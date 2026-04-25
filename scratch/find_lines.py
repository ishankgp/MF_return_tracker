with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '<nav class="navbar' in line or '</nav>' in line or 'id="tableViewContainer"' in line or 'id="comparisonViewContainer"' in line or 'id="research-section"' in line or '<script>' in line or '</script>' in line or 'id="noteForm"' in line or 'class="notes-section"' in line:
        print(f'{i+1}: {line.strip()}')
