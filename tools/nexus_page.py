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
        if not isinstance(body.get('summary'), str) or not isinstance(body.get('description'), str):
            return {'text_available': False, 'cause': 'Nexus v1 reply omits the full summary/description', 'mod_id': body['mod_id'], 'game_id': body['game_id']}
        body['text_available'] = True
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
    parser.add_argument('--replace-unpublished-text', action='store_true', help='Write newly authorized text when unpublished full text cannot be read; inspect the retained receipt before retry')
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
        if before_text.get('text_available') is False:
            require(parent[0]['status'] == 'not_published', 'Published Nexus page text is unavailable; cannot confirm it')
            ack_path = ROOT / 'docs/nexus-page-ack.json'
            require(ack_path.is_file(), 'Unpublished page text unavailable and no retained PATCH acknowledgment; inspect before writing')
            ack = json.loads(ack_path.read_text(encoding='utf-8'))
            require(ack.get('uid') == uid and ack.get('scoped') == scoped and ack.get('patch_acknowledged') is True, 'Retained Nexus PATCH acknowledgment differs from this page/text')
            if ack.get('description_sha256') != receipt['description_sha256']:
                require(args.replace_unpublished_text, 'Retained Nexus PATCH acknowledgment differs from this page/text')
                receipt.update(description_readback_confirmed=False, text_readback_api='v1 unavailable', previous_description_sha256=ack.get('description_sha256'))
                if not args.execute:
                    print(json.dumps({'operation': 'Rejoin text preflight', 'write_attempted': False, 'description_readback_confirmed': False, 'change_pending': True}))
                    return
                receipt['attempted'] = True
                output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
                api('PATCH', '/mods/' + uid, {'summary': summary, 'description': description})
                receipt['patch_acknowledged'] = True
                after_text = read_text()
                if after_text.get('text_available') is False:
                    receipt['confirmed'] = True
                    print('warn: new unpublished page text PATCH acknowledged; full text readback unavailable; inspect this receipt before retry')
                else:
                    require(canonical_text(after_text['summary']) == canonical_text(summary) and canonical_text(after_text['description']) == canonical_text(description), 'Nexus description/summary readback differs; inspect before retry')
                    receipt.update(confirmed=True, description_readback_confirmed=True, text_readback_api='v1')
                print(json.dumps({'operation': 'Rejoin authorized text replacement', 'patch_acknowledged': True, 'description_readback_confirmed': receipt['description_readback_confirmed']}))
                return
            receipt.update(confirmed=True, patch_acknowledged=True, adopted_source_run=ack['source_run'], description_readback_confirmed=False, text_readback_api='v1 unavailable')
            print('warn: unpublished Nexus full text is unavailable; retained PATCH acknowledgment adopted for this exact description; no write replay')
            print(json.dumps({'operation': 'Rejoin page text acknowledgment', 'confirmed': True, 'description_readback_confirmed': False, 'parent_status': 'not_published'}))
            return
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
        receipt['description_readback_confirmed'] = True
        print(json.dumps({'operation': 'Rejoin page text', 'confirmed': True, 'early_development_state': True, 'parent_status': parent[0]['status']}))
    except Exception as error:
        receipt['failure'] = {'cause': str(error), 'retry_requires_readback': True}
        raise
    finally:
        output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
