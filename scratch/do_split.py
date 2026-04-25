import os

def do_split():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    os.makedirs('templates/partials', exist_ok=True)
    
    with open('templates/partials/_navbar.html', 'w', encoding='utf-8') as f:
        f.writelines(lines[22:36])
        
    with open('templates/partials/_portfolio_table.html', 'w', encoding='utf-8') as f:
        f.writelines(lines[87:541])
        
    with open('templates/partials/_comparison_matrix.html', 'w', encoding='utf-8') as f:
        f.writelines(lines[542:936])
        
    with open('templates/partials/_research_tab.html', 'w', encoding='utf-8') as f:
        f.writelines(lines[937:1013])
        
    with open('templates/partials/_notes.html', 'w', encoding='utf-8') as f:
        f.writelines(lines[1013:1038])
        
    with open('static/app.js', 'w', encoding='utf-8') as f:
        f.writelines(lines[1047:1459])
        
    new_index = lines[:22]
    new_index.append('    {% include "partials/_navbar.html" %}\n')
    new_index.extend(lines[36:87])
    new_index.append('                {% include "partials/_portfolio_table.html" %}\n')
    new_index.append('                {% include "partials/_comparison_matrix.html" %}\n')
    new_index.append('            </div>\n\n')
    new_index.append('            {% include "partials/_research_tab.html" %}\n')
    new_index.append('        </div>\n\n')
    new_index.append('        {% include "partials/_notes.html" %}\n\n')
    new_index.extend(lines[1038:1047])
    new_index.append('        <script src="{{ url_for(\'static\', filename=\'app.js\') }}"></script>\n')
    new_index.extend(lines[1459:])
    
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.writelines(new_index)

if __name__ == "__main__":
    do_split()
