"""Update only the configured Rejoin page text and confirm the saved fields."""
from pathlib import Path
import argparse
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.request
from nexus_draft import api, require

ROOT = Path(__file__).resolve().parents[1]

def canonical_text(value):
    require(isinstance(value, str), 'Nexus text field is missing or not a string')
    value = html.unescape(value).replace('\r\n', '\n')
    value = re.sub(r'\r?<br\s*/?>', '\n', value, flags=re.IGNORECASE)
    return value.replace('\r', '\n').strip()

def read_text():
    key = os.environ.get('NEXUSMODS_API_KEY', '')
    require(bool(key), 'NEXUSMODS_API_KEY is missing')
    url = 'https://api.nexusmods.com/v1/games/thecabingame/mods/2.json'
    request = urllib.request.Request(url, headers={'apikey': key, 'accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read())
        require(isinstance(body, dict) and str(body.get('mod_id')) == '2' and str(body.get('game_id')) == '10562', 'Nexus v1 text identity differs')
        require(isinstance(body.get('summary'), str) and isinstance(body.get('description'), str), 'Nexus v1 full text is unavailable')
        return body
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'error: Nexus text GET /v1/games/thecabingame/mods/2.json HTTP {error.code}; original cause={str(error.reason).replace(key, "[redacted]")}') from error
    except urllib.error.URLError as error:
        raise RuntimeError('error: Nexus text GET failed: ' + str(error.reason).replace(key, '[redacted]')) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError('error: Nexus text GET returned invalid JSON') from error

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    uid = os.environ.get('NEXUS_MOD_ID', '')
    scoped = os.environ.get('NEXUS_GAME_SCOPED_ID', '')
    require(uid == '45363444580354' and scoped == '2', 'Configured Rejoin Nexus identity differs')
    before = api('GET', '/games/thecabingame/mods/2')
    require(str(before.get('id')) == uid and str(before.get('game_id')) == '10562' and str(before.get('game_scoped_id')) == scoped, 'Nexus page identity differs')
    parent = api('POST', '/mods/batch', {'mod_ids': [uid]})['mods']
    require(len(parent) == 1 and str(parent[0]['id']) == uid and parent[0]['status'] in {'published', 'not_published'}, 'Nexus page unavailable or unexpected status')
    before_text = read_text()
    summary = re.sub(r'\s+', ' ', (ROOT / 'docs/nexus-summary.txt').read_text(encoding='utf-8')).strip()
    description = (ROOT / 'docs/nexus-description.bbcode').read_text(encoding='utf-8').strip()
    require(1 <= len(summary) <= 350 and description and 'early development state' in description.lower(), 'Release text missing early development disclosure')
    output = ROOT / 'dist/nexus-page.json'
    output.parent.mkdir(exist_ok=True)
    receipt = {'identity': {'uid': uid, 'scoped': scoped}, 'attempted': False, 'confirmed': False,
               'parent_status_before': parent[0]['status'], 'description_sha256': hashlib.sha256(description.encode()).hexdigest()}
    try:
        if not args.execute:
            print(json.dumps({'operation': 'Rejoin page text preflight', 'confirmed': True, 'parent_status': parent[0]['status'], 'write_attempted': False}))
            return
        if canonical_text(before_text['summary']) == canonical_text(summary) and canonical_text(before_text['description']) == canonical_text(description):
            receipt['confirmed'] = True
            receipt['already_current'] = True
        else:
            receipt['attempted'] = True
            output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
            api('PATCH', '/mods/' + uid, {'summary': summary, 'description': description})
            receipt['patch_acknowledged'] = True
            after = api('GET', '/games/thecabingame/mods/2')
            require(str(after.get('id')) == uid and str(after.get('game_scoped_id')) == scoped, 'Nexus text readback identity differs')
            after_text = read_text()
            require(canonical_text(after_text['summary']) == canonical_text(summary) and canonical_text(after_text['description']) == canonical_text(description), 'Nexus description/summary readback differs; inspect before retry')
            receipt['confirmed'] = True
        receipt['text_readback_api'] = 'v1'
        print(json.dumps({'operation': 'Rejoin page text', 'confirmed': True, 'early_development_state': True, 'parent_status': parent[0]['status']}))
    except Exception as error:
        receipt['failure'] = {'cause': str(error), 'retry_requires_readback': True}
        raise
    finally:
        output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
