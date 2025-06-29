# rag_documentation_system.py

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple
import fnmatch
from llm import ask_llm
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

class CodebaseRAG:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path).resolve()
        self.cache_dir = self.root_path / ".rag_cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # File extensions to analyze
        self.code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.html', '.css', '.scss', '.sass', '.vue', '.svelte', '.sql',
            '.sh', '.bash', '.ps1', '.yaml', '.yml', '.json', '.xml', '.toml'
        }
        
        # Files to ignore
        self.ignore_patterns = [
            '__pycache__', '.git', '.vscode', '.idea', 'node_modules',
            '*.pyc', '*.pyo', '*.pyd', '.DS_Store', 'Thumbs.db',
            '.env', '.env.*', '*.log', '*.tmp', '*.cache',
            '.rag_cache', 'venv', 'env', '.venv'
        ]
        
        # Documentation templates
        self.templates = {
            'readme': """# {project_name}

## Overview
{overview}

## Project Structure
{structure}

## Key Components
{components}

## Installation & Setup
{installation}

## Usage
{usage}

## API Documentation
{api_docs}

## Dependencies
{dependencies}

## Contributing
{contributing}

## License
{license}
""",
            
            'api_docs': """# API Documentation

## Endpoints
{endpoints}

## Classes
{classes}

## Functions
{functions}

## Data Models
{models}
""",
            
            'component_doc': """# {component_name}

## Description
{description}

## Functions/Methods
{methods}

## Usage Examples
{examples}

## Dependencies
{dependencies}
"""
        }

    def should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        path_str = str(path)
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(path_str, pattern):
                return True
        return False

    def get_file_hash(self, file_path: Path) -> str:
        """Generate hash for file content to check for changes."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return ""

    def load_cache(self) -> Dict:
        """Load cached analysis results."""
        cache_file = self.cache_dir / "analysis_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_cache(self, cache_data: Dict):
        """Save analysis results to cache."""
        cache_file = self.cache_dir / "analysis_cache.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def scan_codebase(self) -> List[Path]:
        """Scan codebase and return list of relevant files."""
        files = []
        
        for root, dirs, filenames in os.walk(self.root_path):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self.should_ignore(Path(root) / d)]
            
            for filename in filenames:
                file_path = Path(root) / filename
                
                if self.should_ignore(file_path):
                    continue
                    
                if file_path.suffix.lower() in self.code_extensions:
                    files.append(file_path)
        
        return files

    def analyze_file(self, file_path: Path, cache: Dict) -> Dict:
        """Analyze a single file and extract relevant information."""
        relative_path = str(file_path.relative_to(self.root_path))
        file_hash = self.get_file_hash(file_path)
        
        # Check cache
        if relative_path in cache and cache[relative_path].get('hash') == file_hash:
            return cache[relative_path]
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except:
            return {'error': 'Could not read file', 'hash': file_hash}
        
        # Prepare prompt for LLM analysis
        prompt = f"""Analyze this code file and provide a structured summary:

File: {relative_path}
Content:
```
{content[:4000]}  # Limit content to avoid token limits
```

Please provide:
1. Brief description of what this file does
2. Key functions/classes/components
3. Dependencies and imports
4. Main purpose and role in the project
5. Any notable patterns or architecture

Format as JSON with keys: description, key_components, dependencies, purpose, notes"""

        print(f"Analyzing {relative_path}...")
        llm_response = ask_llm(prompt)
        
        result = {
            'hash': file_hash,
            'path': relative_path,
            'size': len(content),
            'lines': len(content.split('\n')),
            'analysis': llm_response,
            'content_preview': content[:500]
        }
        
        return result

    def analyze_codebase_parallel(self, max_workers: int = 4) -> Dict:
        """Analyze entire codebase using parallel processing."""
        files = self.scan_codebase()
        cache = self.load_cache()
        results = {}
        
        print(f"Found {len(files)} files to analyze...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self.analyze_file, file_path, cache): file_path
                for file_path in files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    relative_path = str(file_path.relative_to(self.root_path))
                    results[relative_path] = result
                    print(f"✓ Completed: {relative_path}")
                except Exception as e:
                    print(f"✗ Error analyzing {file_path}: {e}")
        
        # Save updated cache
        self.save_cache(results)
        return results

    def generate_project_overview(self, analysis_results: Dict) -> str:
        """Generate high-level project overview."""
        # Prepare summary of all files for LLM
        file_summaries = []
        for path, result in analysis_results.items():
            if 'analysis' in result:
                file_summaries.append(f"File: {path}\nAnalysis: {result['analysis'][:300]}...")
        
        summaries_text = "\n\n".join(file_summaries[:20])  # Limit to avoid token limits
        
        prompt = f"""Based on the following code analysis, generate a comprehensive project overview:

{summaries_text}

Please provide:
1. Project name and main purpose
2. Architecture overview
3. Key technologies and frameworks used
4. Main components and their relationships
5. Project structure explanation

Format as a well-structured markdown overview."""
        
        return ask_llm(prompt)

    def generate_readme(self, analysis_results: Dict) -> str:
        """Generate comprehensive README.md file."""
        project_name = self.root_path.name.replace('_', ' ').replace('-', ' ').title()
        
        # Generate different sections
        overview = self.generate_project_overview(analysis_results)
        
        # Generate project structure
        structure_prompt = f"""Based on these files, create a clean project structure tree:

Files: {', '.join(list(analysis_results.keys())[:30])}

Show the directory structure in a clear, organized way."""
        
        structure = ask_llm(structure_prompt)
        
        # Generate installation/setup instructions
        setup_prompt = f"""Based on the project analysis, suggest installation and setup instructions:

Project files suggest: {', '.join([k for k in analysis_results.keys() if any(ext in k for ext in ['.py', '.js', '.json', '.yaml', '.requirements'])][:10])}

Provide clear, step-by-step setup instructions."""
        
        installation = ask_llm(setup_prompt)
        
        # Fill template
        readme_content = self.templates['readme'].format(
            project_name=project_name,
            overview=overview,
            structure=structure,
            components="Generated from code analysis",
            installation=installation,
            usage="See individual component documentation",
            api_docs="See API documentation file",
            dependencies="Extracted from project files",
            contributing="Contributions welcome! Please read the code structure first.",
            license="Please specify license"
        )
        
        return readme_content

    def generate_component_docs(self, analysis_results: Dict):
        """Generate documentation for individual components."""
        docs_dir = self.root_path / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        for file_path, analysis in analysis_results.items():
            if 'analysis' in analysis and analysis['analysis']:
                # Generate detailed documentation for each component
                component_name = Path(file_path).stem
                
                doc_prompt = f"""Create detailed documentation for this code component:

File: {file_path}
Analysis: {analysis['analysis']}
Code preview: {analysis.get('content_preview', '')}

Generate comprehensive documentation including:
1. Purpose and functionality
2. Key methods/functions with descriptions
3. Usage examples where applicable
4. Dependencies and relationships
5. Configuration options if any

Format as clean markdown."""
                
                doc_content = ask_llm(doc_prompt)
                
                # Save component documentation
                doc_file = docs_dir / f"{component_name}.md"
                try:
                    with open(doc_file, 'w', encoding='utf-8') as f:
                        f.write(doc_content)
                    print(f"Generated documentation: {doc_file}")
                except Exception as e:
                    print(f"Error saving {doc_file}: {e}")

    def generate_all_documentation(self):
        """Main method to generate all documentation."""
        print("🚀 Starting RAG Documentation Generation...")
        start_time = time.time()
        
        # Step 1: Analyze codebase
        print("\n📊 Analyzing codebase...")
        analysis_results = self.analyze_codebase_parallel()
        
        # Step 2: Generate README
        print("\n📝 Generating README.md...")
        readme_content = self.generate_readme(analysis_results)
        readme_file = self.root_path / "README.md"
        
        try:
            with open(readme_file, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            print(f"✅ Generated: {readme_file}")
        except Exception as e:
            print(f"❌ Error saving README: {e}")
        
        # Step 3: Generate component documentation
        print("\n📚 Generating component documentation...")
        self.generate_component_docs(analysis_results)
        
        # Step 4: Generate API documentation if applicable
        print("\n🔧 Generating API documentation...")
        api_files = [k for k, v in analysis_results.items()
                    if 'api' in k.lower() or 'endpoint' in v.get('analysis', '').lower()]
        
        if api_files:
            api_prompt = f"""Generate API documentation based on these files:

{chr(10).join([f"File: {f}, Analysis: {analysis_results[f].get('analysis', '')[:200]}..." for f in api_files[:5]])}

Create comprehensive API documentation with endpoints, parameters, and examples."""
            
            api_docs = ask_llm(api_prompt)
            api_file = self.root_path / "API_DOCUMENTATION.md"
            
            try:
                with open(api_file, 'w', encoding='utf-8') as f:
                    f.write(api_docs)
                print(f"✅ Generated: {api_file}")
            except Exception as e:
                print(f"❌ Error saving API docs: {e}")
        
        end_time = time.time()
        print(f"\n🎉 Documentation generation completed in {end_time - start_time:.2f} seconds!")
        print(f"📁 Check the following files:")
        print(f"   - README.md")
        print(f"   - docs/ directory for component documentation")
        if api_files:
            print(f"   - API_DOCUMENTATION.md")

def main():
    """Main function to run the RAG documentation system."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate documentation using RAG system")
    parser.add_argument("--path", "-p", default=".", help="Path to project root")
    parser.add_argument("--workers", "-w", type=int, default=4, help="Number of parallel workers")
    
    args = parser.parse_args()
    
    rag_system = CodebaseRAG(args.path)
    rag_system.generate_all_documentation()

if __name__ == "__main__":
    main()
