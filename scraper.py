import re
import requests
from bs4 import BeautifulSoup


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(?:0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}|\+81[-\s]?\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4})')

TITLE_WORDS = ['教授', '准教授', '講師', '助教', '助手', '名誉教授', 'Professor', 'Associate Professor', 'Lecturer']


def fetch_html(url, timeout=15):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        # encoding detection
        if resp.encoding and resp.encoding.lower() in ('shift_jis', 'shift-jis', 'sjis', 'ms932', 'cp932'):
            resp.encoding = 'cp932'
        elif resp.encoding and resp.encoding.lower() in ('euc-jp', 'euc_jp'):
            resp.encoding = 'euc-jp'
        else:
            resp.encoding = resp.apparent_encoding or 'utf-8'
        return resp.text
    except Exception as e:
        return None


def parse_professors(html, base_url=''):
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Try to find structured professor blocks
    # Strategy: look for elements containing title words near a name
    candidates = []

    for tag in soup.find_all(['td', 'div', 'li', 'article', 'section', 'tr']):
        text = tag.get_text(' ', strip=True)
        if any(word in text for word in TITLE_WORDS):
            candidates.append(tag)

    seen_names = set()

    for block in candidates:
        text = block.get_text(' ', strip=True)

        # Extract title
        title = ''
        for word in TITLE_WORDS:
            if word in text:
                title = word
                break

        # Extract name: look for Japanese name pattern (2-4 kanji, optional space, 2-4 kanji)
        name = ''
        name_match = re.search(r'[\u4e00-\u9fff]{2,4}[\s\u3000]*[\u4e00-\u9fff]{2,4}', text)
        if name_match:
            name = name_match.group().replace('\u3000', ' ').strip()

        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # Extract email
        email_match = EMAIL_RE.search(text)
        email = email_match.group() if email_match else ''

        # Extract phone
        phone_match = PHONE_RE.search(text)
        phone = phone_match.group() if phone_match else ''

        # Extract photo URL
        photo_url = ''
        img = block.find('img')
        if img and img.get('src'):
            src = img['src']
            if src.startswith('http'):
                photo_url = src
            elif src.startswith('//'):
                photo_url = 'https:' + src
            elif base_url:
                from urllib.parse import urljoin
                photo_url = urljoin(base_url, src)

        # Extract specialty: look for research keywords
        specialty = ''
        for kw in ['専門', '研究分野', '研究領域', 'キーワード']:
            idx = text.find(kw)
            if idx != -1:
                snippet = text[idx:idx+80].split('。')[0].split('\n')[0]
                specialty = snippet.strip()
                break

        results.append({
            'name': name,
            'title': title,
            'email': email,
            'phone': phone,
            'photo_url': photo_url,
            'specialty': specialty,
            'source_url': base_url,
        })

    return results


def scrape_university(url):
    html = fetch_html(url)
    if not html:
        return [], 'URLの取得に失敗しました'
    professors = parse_professors(html, base_url=url)
    return professors, None


def scrape_department(url):
    return scrape_university(url)
