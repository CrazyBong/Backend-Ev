import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app

def generate_docs():
    schema = app.openapi()
    os.makedirs('Docs', exist_ok=True)
    
    with open('Docs/endpoints.md', 'w', encoding='utf-8') as f:
        f.write('# ⚡ EVChargeFinder Frontend API Map\n\n')
        f.write('This document outlines the core endpoints needed for the React Native App connection. Admin and IoT physical device webhooks have been excluded for clarity.\n\n')
        f.write('---\n\n')
        
        # Group paths by their tags
        grouped_endpoints = {}
        for path, methods in schema['paths'].items():
            # Skip Admin and IoT as they are irrelevant for the APK
            if '/admin/' in path.lower() or '/iot/' in path.lower():
                continue
                
            for method, details in methods.items():
                tag = details.get('tags', ['General'])[0]
                if tag not in grouped_endpoints:
                    grouped_endpoints[tag] = []
                grouped_endpoints[tag].append((path, method, details))
                
        # Write by tag domain
        for tag, endpoints in sorted(grouped_endpoints.items()):
            f.write(f'## 📦 Domain: {tag}\n\n')
            
            for path, method, details in endpoints:
                f.write(f'### `{method.upper()} {path}`\n')
                f.write(f'> **{details.get("summary", "No summary")}**\n\n')
                
                # Request Query Parameters
                params = details.get('parameters', [])
                if params:
                    f.write('**Query Parameters:**\n')
                    for p in params:
                        if p.get('in') == 'query':
                            required = '(Required)' if p.get('required') else '(Optional)'
                            f.write(f'- `{p["name"]}` {required}\n')
                    f.write('\n')

                # Note if Authorization is required
                if 'security' in details:
                    f.write('- 🔐 **Auth Required**: Bearer Token (JWT)\n\n')
                
                f.write('---\n\n')

if __name__ == '__main__':
    generate_docs()
    print("Successfully generated React Native documentation at Docs/endpoints.md")
