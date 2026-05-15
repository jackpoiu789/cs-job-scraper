import asyncio
import sys
import os
import datetime
import subprocess
import pandas as pd
from playwright.async_api import async_playwright
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

# 本機執行時載入 .env，雲端執行時從環境變數讀取
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT", "")

_today = datetime.date.today().strftime("%Y%m%d")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Crawl_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT = os.path.join(OUTPUT_DIR, f"customer_success_jobs_{_today}.xlsx")

MAX_JOBS = 50
KEYWORDS = ["customer success", "客戶成功", "csm", "customer success manager"]

def is_cs_title(title: str) -> bool:
    return any(k in title.lower() for k in KEYWORDS)

# ──────────────────────────────────────────────
# 104 人力銀行
# ──────────────────────────────────────────────

async def fetch_104_jobs(browser, max_jobs=MAX_JOBS):
    jobs = []
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="zh-TW",
        viewport={"width": 1280, "height": 800},
    )
    page = await context.new_page()

    print("\n========== 104 人力銀行 ==========")
    await page.goto("https://www.104.com.tw/", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(2)

    page_num = 1
    while len(jobs) < max_jobs:
        url = (
            f"https://www.104.com.tw/jobs/search/"
            f"?keyword=customer+success&order=15&asc=0&page={page_num}&mode=s"
        )
        print(f"\n第 {page_num} 頁...")
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(3)

        cards = await page.evaluate("""
            () => {
                const seen = new Set();
                const results = [];
                document.querySelectorAll('a[href*="/job/"]').forEach(a => {
                    const href = a.href;
                    if (!href.includes('/job/') || seen.has(href)) return;
                    const title = a.innerText.trim().split('\\n')[0].trim();
                    if (!title) return;
                    seen.add(href);

                    const card = a.closest('article') ||
                                 a.closest('li') ||
                                 a.closest('[class*="job-list"]') ||
                                 a.parentElement?.parentElement?.parentElement;

                    const companyEl = card?.querySelector(
                        'a[href*="custno"], a[href*="/company/"], [class*="company"] a, [class*="cust"] a'
                    );
                    const company = companyEl?.innerText?.trim() || '';

                    const listItems = Array.from(card?.querySelectorAll('li, span') || [])
                        .map(el => el.innerText.trim())
                        .filter(t => t.length > 0 && t.length < 30);

                    const salary = listItems.find(t =>
                        t.includes('萬') || t.includes('月薪') || t.includes('年薪') ||
                        t.includes('面議') || t.includes('薪')
                    ) || '';

                    const locationKeywords = ['台北','台中','台南','高雄','新北','桃園','新竹','苗栗',
                        '彰化','雲林','嘉義','屏東','宜蘭','花蓮','台東','澎湖','基隆','南投',
                        '遠端','台灣','全台'];
                    const location = listItems.find(t =>
                        locationKeywords.some(k => t.includes(k))
                    ) || '';

                    results.push({ title, href, company, location, salary });
                });
                return results;
            }
        """)

        seen_links = {j["連結"] for j in jobs}
        new_count = 0
        for item in cards:
            title = item.get("title", "")
            link = item.get("href", "")
            if not title or not link or link in seen_links:
                continue
            seen_links.add(link)
            if not is_cs_title(title):
                continue
            jobs.append({
                "職稱": title,
                "公司": item.get("company", ""),
                "地點": item.get("location", ""),
                "薪資": item.get("salary", ""),
                "連結": link,
            })
            new_count += 1
            print(f"  [104] {title} | {item.get('company','')} | {item.get('location','')}")
            if len(jobs) >= max_jobs:
                break

        print(f"  本頁新增 {new_count} 筆，累計：{len(jobs)} 筆")
        if not cards or new_count == 0:
            print("  已無新職缺，停止。")
            break
        page_num += 1

    await context.close()
    return jobs

# ──────────────────────────────────────────────
# LinkedIn（Cookie 登入，無需帳密）
# ──────────────────────────────────────────────

async def fetch_linkedin_jobs(browser, max_jobs=MAX_JOBS):
    jobs = []
    seen_links = set()

    if not LINKEDIN_LI_AT:
        print("\n[!] 未設定 LINKEDIN_LI_AT，跳過 LinkedIn 爬取")
        return jobs

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="zh-TW",
        viewport={"width": 1280, "height": 800},
    )
    await context.add_cookies([{
        "name": "li_at",
        "value": LINKEDIN_LI_AT,
        "domain": ".linkedin.com",
        "path": "/",
    }])
    page = await context.new_page()
    await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

    print("\n========== LinkedIn ==========")
    print("使用 Cookie 登入，驗證中...")
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    if "login" in page.url or "authwall" in page.url:
        print("[!] Cookie 已過期，請更新 LINKEDIN_LI_AT")
        await context.close()
        return jobs
    print("登入成功！")

    start = 0
    while len(jobs) < max_jobs:
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords=customer%20success&location=Taiwan&start={start}"
        )
        print(f"\n第 {start // 25 + 1} 頁（start={start}）")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)

        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(1)

        cards = await page.evaluate("""
            () => {
                const results = [];
                const seen = new Set();
                document.querySelectorAll('div[data-job-id]').forEach(card => {
                    const linkEl = card.querySelector('a[href*="/jobs/view/"]');
                    const href = (linkEl?.href || '').split('?')[0];
                    if (!href || seen.has(href)) return;
                    seen.add(href);

                    const titleSpan = linkEl?.querySelector('span[aria-hidden="true"]');
                    const title = (titleSpan?.innerText || linkEl?.innerText || '').trim();

                    const companyEl = card.querySelector(
                        '.job-card-container__primary-description, ' +
                        'span.job-card-container__primary-description, ' +
                        '.artdeco-entity-lockup__subtitle span, ' +
                        '[class*="subtitle"] span'
                    );
                    const company = companyEl?.innerText?.trim() || '';

                    const locationEl = card.querySelector(
                        'li.job-card-container__metadata-item, ' +
                        '[class*="metadata-item"] li, ' +
                        '[class*="metadata"] li'
                    );
                    const location = locationEl?.innerText?.trim() || '';

                    if (title && href) results.push({ title, href, company, location });
                });
                return results;
            }
        """)

        if not cards:
            print("  此頁無職缺卡片，停止。")
            break

        new_count = 0
        for item in cards:
            title = item.get("title", "").strip()
            link = item.get("href", "").strip()
            company = item.get("company", "").strip()
            if not title or not link or link in seen_links:
                continue
            seen_links.add(link)
            if company.upper() == "TP":  # CLAUDE.md 規則 6：跳過 TP
                continue
            if not is_cs_title(title):
                continue
            jobs.append({
                "職稱": title,
                "公司": company,
                "地點": item.get("location", "").strip(),
                "薪資": "詳見職缺頁",
                "連結": link,
            })
            new_count += 1
            print(f"  [LI] {title} | {company} | {item.get('location','')}")
            if len(jobs) >= max_jobs:
                break

        print(f"  本頁新增 {new_count} 筆，累計：{len(jobs)} 筆")
        if new_count == 0:
            print("  本頁無新職缺，停止。")
            break
        start += 25

    await context.close()
    return jobs

# ──────────────────────────────────────────────
# 存檔
# ──────────────────────────────────────────────

def save_to_excel(jobs_104, jobs_linkedin, output_path):
    col_widths = [42, 30, 15, 20, 65]
    cols = ["A", "B", "C", "D", "E"]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(jobs_104).to_excel(writer, sheet_name="104", index=False)
        ws = writer.sheets["104"]
        for col, w in zip(cols, col_widths):
            ws.column_dimensions[col].width = w

        pd.DataFrame(jobs_linkedin).to_excel(writer, sheet_name="LinkedIn", index=False)
        ws = writer.sheets["LinkedIn"]
        for col, w in zip(cols, col_widths):
            ws.column_dimensions[col].width = w

    print(f"\n========== 完成 ==========")
    print(f"104：{len(jobs_104)} 筆")
    print(f"LinkedIn：{len(jobs_linkedin)} 筆")
    print(f"已儲存至：{output_path}")

def git_push_results(output_path):
    repo_root = os.path.dirname(__file__)
    try:
        subprocess.run(["git", "add", output_path], cwd=repo_root, check=True)
        msg = f"Update job listings {_today}"
        subprocess.run(["git", "commit", "-m", msg], cwd=repo_root, check=True)
        subprocess.run(["git", "push"], cwd=repo_root, check=True)
        print("結果已推送至 GitHub")
    except subprocess.CalledProcessError as e:
        print(f"Git push 失敗：{e}")

# ──────────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────────

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--lang=zh-TW", "--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage"]
        )
        jobs_104 = await fetch_104_jobs(browser, max_jobs=MAX_JOBS)
        jobs_linkedin = await fetch_linkedin_jobs(browser, max_jobs=MAX_JOBS)
        await browser.close()

    save_to_excel(jobs_104, jobs_linkedin, OUTPUT)

    # 雲端環境自動 git push
    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS") or os.getenv("CCR_ENV"):
        git_push_results(OUTPUT)

if __name__ == "__main__":
    asyncio.run(main())
