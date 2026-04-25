import os

def refactor_templates():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    navbar_lines = lines[22:35]
    table_view_lines = lines[87:542]
    comparison_view_lines = lines[542:937]
    research_section_lines = lines[937:1013]
    notes_lines = lines[1013:1039]
    js_lines = lines[1047:1459]
    
    # Create partials
    os.makedirs('templates/partials', exist_ok=True)
    with open('templates/partials/_navbar.html', 'w', encoding='utf-8') as f:
        f.writelines(navbar_lines)
    with open('templates/partials/_portfolio_table.html', 'w', encoding='utf-8') as f:
        f.writelines(table_view_lines)
    with open('templates/partials/_comparison_matrix.html', 'w', encoding='utf-8') as f:
        f.writelines(comparison_view_lines)
    with open('templates/partials/_research_tab.html', 'w', encoding='utf-8') as f:
        f.writelines(research_section_lines)
    with open('templates/partials/_notes.html', 'w', encoding='utf-8') as f:
        f.writelines(notes_lines)
        
    # Extract JS
    with open('static/app.js', 'w', encoding='utf-8') as f:
        f.writelines(js_lines)
        
    # Reconstruct index.html
    new_index = lines[:22]
    new_index.append('    {% include "partials/_navbar.html" %}\n')
    new_index.extend(lines[35:87])
    new_index.append('                            {% include "partials/_portfolio_table.html" %}\n')
    new_index.append('                            {% include "partials/_comparison_matrix.html" %}\n')
    new_index.extend(lines[937:937]) # just in case
    # actually, lines[542:937] were comparison view, lines[87:542] were table view.
    # so we replaced lines[87:937]
    new_index.append('            {% include "partials/_research_tab.html" %}\n')
    new_index.extend(lines[1013:1013])
    # The div for section tabs content closes right after comparison view at 936
    # Wait, the structure was:
    # 86: <div class="tab-pane fade show active" id="portfolio-section" ...>
    # 87: <div class="card shadow-sm" id="tableViewContainer">
    # 936: </div>
    # 937: <!-- RESEARCH SECTION -->
    
    # We should reconstruct carefully.
    return "done"

if __name__ == "__main__":
    refactor_templates()
