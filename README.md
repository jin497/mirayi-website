# Mirayi website

A fast static site (no database, no monthly builder fee). Same URLs, titles, descriptions and keywords as the old Wix site.
You edit it in the browser at **https://www.mirayi.my/admin** (set up once, see below), or ask Claude.

## Folder map

| Folder / file | What it is |
|---|---|
| `content/` | **Everything you edit**: `works.json`, `home.json`, `seo.json`, `settings.json`, `posts/*.md`, plus `zh/`, `ko/`, `ja/` (translated pages) |
| `admin/` | The editor page (`/admin`) and its menu (`config.yml`) |
| `functions/api/` | Tiny login helper for the editor (runs free on Cloudflare) |
| `_tools/build.py` | Turns `content/` into the website pages |
| `_tools/download_images.py` | Copies your images off Wix (run once, before cancelling Wix) |
| `assets/` | Styles and scripts. `assets/works.js` and `assets/config.js` are generated. |
| `*.html`, `post/`, `sitemap.xml` | Generated website. Do not edit by hand. |

## One-time setup (about 30 minutes)

1. **Download the images** (while Wix is still active), on your computer:
   `pip install -r requirements.txt`, then `python3 _tools/download_images.py`, then `python3 _tools/build.py`.
   The build shrinks every picture to WebP (max 1600 px, originals moved to `_originals/`, which you do not upload) and uses them;
   any image still missing keeps loading from Wix. New pictures you upload in `/admin` are shrunk automatically on every publish.
2. **Create a free GitHub account** and a new **private** repository called `mirayi-website`. Upload this whole folder to it
   (GitHub → Add file → Upload files, including the `assets/img` folder). Keep the branch name `main`.
3. **Open `admin/config.yml`** and change `repo: YOUR-GITHUB-USERNAME/mirayi-website` to your real name, e.g. `repo: jinchongng/mirayi-website`.
4. **Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git** → choose the repository. Build settings:
   - Build command: `pip install -r requirements.txt && python3 _tools/build.py`
   - Build output directory: `.` (a single dot)
5. **Make the login work.** On GitHub: Settings → Developer settings → OAuth Apps → New OAuth App.
   - Homepage URL: `https://www.mirayi.my`
   - Authorization callback URL: `https://www.mirayi.my/api/callback`
   Copy the *Client ID*, generate a *Client secret*. In Cloudflare: your Pages project → Settings → Variables and Secrets,
   add `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` (secret), then redeploy.
6. **Connect the domain** (Pages project → Custom domains → `www.mirayi.my`; leave every other DNS record alone,
   including `kitsu` and the email records). Add the redirect `mirayi.my/*` → `https://www.mirayi.my/$1` (301).
7. In Google Search Console and Bing Webmaster Tools submit `https://www.mirayi.my/sitemap.xml`. Keep Wix a few days, then cancel.

## Editing yourself

Open `https://www.mirayi.my/admin` → **Login with GitHub**. You will see:

- **Blog posts**: add, edit, delete. Write in the editor, drag in pictures.
- **Website content → Portfolio works**: add / remove / reorder works; choose *Mirayi IP* or *Services work*; upload the picture; paste the YouTube link.
- **Website content → Homepage**: slideshow pictures, headline, client logos, story text, testimonial, rebate text.
- **Website content → Google titles and descriptions**: the SEO text of every page.
- **Website content → Contact form settings**.

Press **Publish** (top right). The site updates by itself in about a minute. Nothing else to do.
Do not change the "Address" fields on the SEO page: changing an address loses the Google ranking for that page.

Not editable in the admin (ask Claude, it takes a minute): the text of the inner pages (Who we are, Our business, Game production, etc.),
the menu, page design and layout.

## Without the admin page

Edit the files in `content/` directly, run `python3 _tools/build.py`, and upload the folder. Preview without installing anything:
double-click `_preview/index.html` (re-create it with `python3 _tools/build.py --preview`).
Preview exactly like the live site: `npx serve .`

## Chinese version (中文版) and Baidu

- The Chinese site lives at `https://www.mirayi.my/zh/` (12 pages: home, about, services, brands, production, series & films, game, commercials,
  visual development, jobs, plus the outsourcing and FIMI guides). The **EN | 中文** switch is in the menu, every English page and its Chinese page
  point to each other with `hreflang` tags, and the sitemap lists both.
- Edit Chinese pages in the admin under **中文页面 (Chinese pages)** and **Website content → 中文首页**. Work captions and titles in Chinese are
  fields on each work. The blog is English only.
- The Chinese pages use no Google services (no Google Fonts), so they load in mainland China. Run `download_images.py` too: the Wix image server can be slow there.
- YouTube is not reachable in mainland China. For each work you can add a **Video link for Chinese visitors** (Bilibili, Youku, Tencent Video); Chinese pages use it instead.
- The contact area shows your **Lark (飞书)** and **WeChat (微信)** QR codes with labels, and says the team communicates in Chinese.
- **Baidu / other Chinese search engines:** sign in at `ziyuan.baidu.com` (Baidu Webmaster Platform), add `https://www.mirayi.my`, choose the HTML-tag
  verification, and paste the code into the admin (**Contact form settings → Baidu site verification code**). Then submit `https://www.mirayi.my/sitemap.xml`.
  Do the same for Sogou, 360 (so.com) and Shenma if you wish. Also add the site to **Bing Webmaster Tools**: Bing is available in China (cn.bing.com).
  Baidu favours websites hosted in mainland China with an ICP licence (备案), which needs a mainland entity, so ranking in Baidu may be slow without it.
  Quick wins outside the website: a WeChat Official Account (公众号), a Bilibili channel with your showreel, Zhihu/Xiaohongshu posts, and the same
  Chinese company description everywhere.

## Korean (한국어) and Japanese (日本語) versions

- Korean lives at `/ko/` and Japanese at `/ja/`, with the same 12 pages as the Chinese version (home, about, services, brands, production,
  series & films, game, commercials, visual development, jobs, and the outsourcing and FIMI guides). The menu switch is **EN | 中文 | 한국어 | 日本語**.
  Every page points to its other-language versions with `hreflang` tags (plus `x-default`), and the sitemap lists them all.
- Edit them in the admin under **한국어 페이지**, **日本語ページ** and **Website content → 한국어 홈 / 日本語ホーム**. Work captions can be
  translated with the optional Korean/Japanese fields on each work (English titles are used when empty).
- The pages say Korean and Japanese enquiries are welcome and that **replies are in English**. Change this wording only if the team can
  really answer in Korean or Japanese. No WeChat/Lark QR codes appear on these pages.
- Korean angle: Mirayi's Korean series and commercials (Tobot V, Carbot, Kongsuni, Anipang, CU) are named on the Korean pages.
- Fonts are the visitor's own system fonts (fast, no Google Fonts). Korean text keeps words together (`word-break: keep-all`), Japanese uses strict line breaking.
- **Naver (Korea):** add the site at `searchadvisor.naver.com`, choose the HTML-tag verification, paste the code into the admin
  (**Contact form settings → Naver site verification code**), then submit `https://www.mirayi.my/sitemap.xml`. Naver also reads RSS; the sitemap is enough to start.
- **Japan:** Google and Bing do most of the work (Yahoo! Japan uses Google's index). Submit the sitemap in Google Search Console as usual.
- Have the Korean and Japanese texts read by a native speaker before announcing them. They were written by Claude.

### Automatic language

On a visitor's **first visit** to an English page that has a translation, the site checks the browser's language list. If the first
language that matches is Chinese (any: China, Taiwan, Hong Kong), Korean or Japanese, the visitor goes to the same page in that language.
It never redirects: search-engine crawlers, visitors whose first language is English, visitors who arrive from another page of this site,
pages without a translation (blog posts), or anyone who has used the language switch before (their choice is remembered).
It uses the browser language, not the country, because that is far more accurate (a Korean speaker in Malaysia, a tourist in Korea) and
keeps Google's rules happy: crawlers always see every version. Taiwan and Hong Kong visitors get the Simplified Chinese pages.

## SEO — what was kept

- All 11 page URLs and 5 blog post URLs are identical to the old site (`/whoweare`, `/gameproduction`, `/post/...`).
- Titles, meta descriptions, keywords, Open Graph and Twitter tags copied exactly per page, plus the Google / Bing / Yandex / Pinterest / Facebook verification tags.
- `sitemap.xml` and `robots.txt` at the same addresses as before (new blog posts are added to the sitemap automatically).
- `_redirects` sends the extra Wix URLs (`/jobs`, `/join-with-us-1`, `/search`) to the nearest new page with a permanent 301.
- Structured data: Organization (home) and BlogPosting (each post).
- Two old typos were kept on purpose so the indexed text does not change: "Oringinal" in the `/mirayibrand` title and "Proviving" in its description.
  You can fix them in the admin's SEO section.
