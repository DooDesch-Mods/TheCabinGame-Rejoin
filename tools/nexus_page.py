"""Update only the configured Rejoin page text and confirm the saved fields."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
from nexus_draft import api, require

ROOT = Path(__file__).resolve().parents[1]

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
        if before.get('summary') == summary and str(before.get('description', '')).strip() == description:
            receipt['confirmed'] = True
            receipt['already_current'] = True
        else:
            receipt['attempted'] = True
            output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
            api('PATCH', '/mods/' + uid, {'summary': summary, 'description': description})
            after = api('GET', '/games/thecabingame/mods/2')
            require(str(after.get('id')) == uid and str(after.get('game_scoped_id')) == scoped, 'Nexus text readback identity differs')
            require(after.get('summary') == summary and str(after.get('description', '')).strip() == description, 'Nexus description/summary readback differs; inspect before retry')
            receipt['confirmed'] = True
        print(json.dumps({'operation': 'Rejoin page text', 'confirmed': True, 'early_development_state': True, 'parent_status': parent[0]['status']}))
    except Exception as error:
        receipt['failure'] = {'cause': str(error), 'retry_requires_readback': True}
        raise
    finally:
        output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
