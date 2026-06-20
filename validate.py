import re

with open('C:/Users/Isaac/Documents/pip/display.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for basic HTML structure
print('=== Basic Structure Checks ===')
print('File length: ' + str(len(content)) + ' chars')
print('Has <html> tag: ' + str('<html' in content))
print('Has </html> tag: ' + str('</html>' in content))
print('Has <head> tag: ' + str('<head>' in content))
print('Has </head> tag: ' + str('</head>' in content))
print('Has <body> tag: ' + str('<body' in content))
print('Has </body> tag: ' + str('</body>' in content))
print('Has <script> tag: ' + str('<script>' in content))
print('Has </script> tag: ' + str('</script>' in content))

# Check for unmatched braces in JS
js_start = content.find('<script>')
js_end = content.find('</script>')
if js_start != -1 and js_end != -1:
    js_code = content[js_start:js_end]
    open_braces = js_code.count('{')
    close_braces = js_code.count('}')
    print('JS braces: ' + str(open_braces) + ' open, ' + str(close_braces) + ' close, balanced: ' + str(open_braces == close_braces))
    
    open_parens = js_code.count('(')
    close_parens = js_code.count(')')
    print('JS parens: ' + str(open_parens) + ' open, ' + str(close_parens) + ' close, balanced: ' + str(open_parens == close_parens))
    
    open_brackets = js_code.count('[')
    close_brackets = js_code.count(']')
    print('JS brackets: ' + str(open_brackets) + ' open, ' + str(close_brackets) + ' close, balanced: ' + str(open_brackets == close_brackets))

# Check for CSS braces
style_start = content.find('<style>')
style_end = content.rfind('</style>')
if style_start != -1 and style_end != -1:
    css_code = content[style_start:style_end]
    css_open = css_code.count('{')
    css_close = css_code.count('}')
    print('CSS braces: ' + str(css_open) + ' open, ' + str(css_close) + ' close, balanced: ' + str(css_open == css_close))

# Check key functions exist
functions = ['renderOptions', 'procesarVersos', 'procesarEstado', 'construirRueda', 'finalSettle', 'mostrarResultadoWheel', 'animateSpin']
for fn in functions:
    if 'function ' + fn in content:
        print('Function ' + fn + ' found')
    else:
        print('Function ' + fn + ' NOT found')

# Check key CSS classes
classes = ['.option-card.selected', '.ruleta-sector-label', '.ruleta-wheel-word-container', '.ruleta-wheel-word']
for cls in classes:
    if cls in content:
        print('CSS class ' + cls + ' found')
    else:
        print('CSS class ' + cls + ' NOT found')

# Check data attributes in renderOptions
if 'data-correct' in content and 'data-selected' in content:
    print('data-correct and data-selected attributes in renderOptions')
else:
    print('data attributes missing')

# Check CSS variables for wheel labels
if '--label-angle' in content and '--label-radius' in content:
    print('CSS variables --label-angle and --label-radius found')
else:
    print('CSS variables missing')

# Check --wc variable for word sizing
if '--wc' in content:
    print('CSS variable --wc found')
else:
    print('CSS variable --wc missing')

print('=== Validation Complete ===')