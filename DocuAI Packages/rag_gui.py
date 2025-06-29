# rag_gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import os
import sys
from pathlib import Path
import json
from datetime import datetime

# Import your RAG system
try:
    from rag_documentation_system import CodebaseRAG
    from llm import get_model_name, ask_llm
except ImportError:
    messagebox.showerror("Import Error", "Please ensure rag_documentation_system.py and llm.py are in the same directory")
    sys.exit(1)

class RAGDocumentationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RAG Documentation Generator")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Variables
        self.project_path = tk.StringVar(value=os.getcwd())
        self.current_model = tk.StringVar(value=get_model_name())
        self.max_workers = tk.IntVar(value=4)
        self.is_running = False
        self.rag_system = None
        
        # Queue for thread communication
        self.progress_queue = queue.Queue()
        
        # Setup GUI
        self.setup_gui()
        self.setup_menu()
        
        # Start checking queue
        self.check_queue()
        
    def setup_menu(self):
        """Setup menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Select Project Folder", command=self.select_project_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Clear Cache", command=self.clear_cache)
        tools_menu.add_command(label="View Generated Files", command=self.view_generated_files)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
    def setup_gui(self):
        """Setup the main GUI layout."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="RAG Documentation Generator",
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Project path selection
        ttk.Label(main_frame, text="Project Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        path_frame.columnconfigure(0, weight=1)
        
        self.path_entry = ttk.Entry(path_frame, textvariable=self.project_path, width=50)
        self.path_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Button(path_frame, text="Browse", command=self.select_project_folder).grid(row=0, column=1)
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        config_frame.columnconfigure(1, weight=1)
        
        # Model selection
        ttk.Label(config_frame, text="LLM Model:").grid(row=0, column=0, sticky=tk.W, pady=2)
        model_frame = ttk.Frame(config_frame)
        model_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        model_frame.columnconfigure(0, weight=1)
        
        self.model_entry = ttk.Entry(model_frame, textvariable=self.current_model)
        self.model_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Button(model_frame, text="Test", command=self.test_model).grid(row=0, column=1)
        
        # Worker threads
        ttk.Label(config_frame, text="Parallel Workers:").grid(row=1, column=0, sticky=tk.W, pady=2)
        worker_frame = ttk.Frame(config_frame)
        worker_frame.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Spinbox(worker_frame, from_=1, to=8, textvariable=self.max_workers, width=10).grid(row=0, column=0)
        ttk.Label(worker_frame, text="(1-8 recommended)").grid(row=0, column=1, padx=(5, 0))
        
        # Generation options
        options_frame = ttk.LabelFrame(main_frame, text="Generation Options", padding="10")
        options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.generate_readme = tk.BooleanVar(value=True)
        self.generate_components = tk.BooleanVar(value=True)
        self.generate_api = tk.BooleanVar(value=True)
        self.use_cache = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(options_frame, text="Generate README.md", variable=self.generate_readme).grid(row=0, column=0, sticky=tk.W)
        ttk.Checkbutton(options_frame, text="Generate Component Docs", variable=self.generate_components).grid(row=0, column=1, sticky=tk.W)
        ttk.Checkbutton(options_frame, text="Generate API Documentation", variable=self.generate_api).grid(row=1, column=0, sticky=tk.W)
        ttk.Checkbutton(options_frame, text="Use Cache (faster)", variable=self.use_cache).grid(row=1, column=1, sticky=tk.W)
        
        # Output area
        output_frame = ttk.LabelFrame(main_frame, text="Output Log", padding="5")
        output_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=15, wrap=tk.WORD)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 5))
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        self.generate_button = ttk.Button(button_frame, text="🚀 Generate Documentation",
                                         command=self.start_generation, style="Accent.TButton")
        self.generate_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="⏹ Stop",
                                     command=self.stop_generation, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="📁 Open Output Folder",
                  command=self.open_output_folder).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="🗑 Clear Log",
                  command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(1, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.file_count_label = ttk.Label(status_frame, text="")
        self.file_count_label.grid(row=0, column=2, sticky=tk.E)
        
        # Configure style for accent button
        self.style.configure("Accent.TButton", foreground="white", background="#0078d4")
        
    def log_message(self, message, level="INFO"):
        """Add message to output log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}\n"
        
        self.output_text.insert(tk.END, formatted_message)
        self.output_text.see(tk.END)
        
        # Color coding
        if level == "ERROR":
            # Get the current position and apply red color
            start = self.output_text.index(f"end-1c linestart")
            end = self.output_text.index(f"end-1c lineend")
            self.output_text.tag_add("error", start, end)
            self.output_text.tag_config("error", foreground="red")
        elif level == "SUCCESS":
            start = self.output_text.index(f"end-1c linestart")
            end = self.output_text.index(f"end-1c lineend")
            self.output_text.tag_add("success", start, end)
            self.output_text.tag_config("success", foreground="green")
        
        self.root.update_idletasks()
        
    def select_project_folder(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(initialdir=self.project_path.get())
        if folder:
            self.project_path.set(folder)
            self.log_message(f"Selected project folder: {folder}")
            self.scan_project_files()
            
    def scan_project_files(self):
        """Scan and count project files."""
        try:
            path = Path(self.project_path.get())
            if not path.exists():
                self.file_count_label.config(text="Invalid path")
                return
                
            # Quick scan for file count
            code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h'}
            count = 0
            for file_path in path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in code_extensions:
                    count += 1
                    
            self.file_count_label.config(text=f"{count} code files found")
        except Exception as e:
            self.file_count_label.config(text="Error scanning files")
            
    def test_model(self):
        """Test connection to LLM model."""
        self.log_message("Testing LLM connection...")
        
        def test_thread():
            try:
                response = ask_llm("Hello, please respond with 'LLM connection successful'")
                if response and "successful" in response.lower():
                    self.progress_queue.put(("log", "LLM connection test successful!", "SUCCESS"))
                else:
                    self.progress_queue.put(("log", f"LLM responded: {response[:100]}...", "INFO"))
            except Exception as e:
                self.progress_queue.put(("log", f"LLM connection failed: {str(e)}", "ERROR"))
                
        threading.Thread(target=test_thread, daemon=True).start()
        
    def start_generation(self):
        """Start documentation generation in a separate thread."""
        if self.is_running:
            return
            
        # Validate inputs
        if not os.path.exists(self.project_path.get()):
            messagebox.showerror("Error", "Please select a valid project folder")
            return
            
        self.is_running = True
        self.generate_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_label.config(text="Generating documentation...")
        self.progress_var.set(0)
        
        # Start generation thread
        threading.Thread(target=self.generation_worker, daemon=True).start()
        
    def generation_worker(self):
        """Worker thread for documentation generation."""
        try:
            # Initialize RAG system
            self.progress_queue.put(("log", "Initializing RAG system...", "INFO"))
            self.progress_queue.put(("progress", 5))
            
            self.rag_system = CodebaseRAG(self.project_path.get())
            
            # Override the print function in RAG system to use our logging
            original_print = print
            def custom_print(*args, **kwargs):
                message = " ".join(str(arg) for arg in args)
                self.progress_queue.put(("log", message, "INFO"))
            
            # Temporarily replace print
            import builtins
            builtins.print = custom_print
            
            try:
                # Step 1: Analyze codebase
                self.progress_queue.put(("log", "Scanning and analyzing codebase...", "INFO"))
                self.progress_queue.put(("progress", 10))
                
                files = self.rag_system.scan_codebase()
                self.progress_queue.put(("log", f"Found {len(files)} files to analyze", "INFO"))
                
                # Analyze with progress updates
                cache = self.rag_system.load_cache() if self.use_cache.get() else {}
                analysis_results = {}
                
                total_files = len(files)
                for i, file_path in enumerate(files):
                    if not self.is_running:  # Check for stop signal
                        break
                        
                    result = self.rag_system.analyze_file(file_path, cache)
                    relative_path = str(file_path.relative_to(Path(self.project_path.get())))
                    analysis_results[relative_path] = result
                    
                    progress = 10 + (i + 1) / total_files * 60  # 10-70%
                    self.progress_queue.put(("progress", progress))
                    self.progress_queue.put(("log", f"Analyzed: {relative_path}", "INFO"))
                
                if not self.is_running:
                    return
                    
                # Save cache
                self.rag_system.save_cache(analysis_results)
                self.progress_queue.put(("progress", 70))
                
                # Step 2: Generate README
                if self.generate_readme.get():
                    self.progress_queue.put(("log", "Generating README.md...", "INFO"))
                    readme_content = self.rag_system.generate_readme(analysis_results)
                    
                    readme_file = Path(self.project_path.get()) / "README.md"
                    with open(readme_file, 'w', encoding='utf-8') as f:
                        f.write(readme_content)
                    
                    self.progress_queue.put(("log", f"Generated: {readme_file}", "SUCCESS"))
                    self.progress_queue.put(("progress", 80))
                
                # Step 3: Generate component docs
                if self.generate_components.get():
                    self.progress_queue.put(("log", "Generating component documentation...", "INFO"))
                    self.rag_system.generate_component_docs(analysis_results)
                    self.progress_queue.put(("progress", 90))
                
                # Step 4: Generate API docs
                if self.generate_api.get():
                    self.progress_queue.put(("log", "Generating API documentation...", "INFO"))
                    api_files = [k for k, v in analysis_results.items()
                               if 'api' in k.lower() or 'endpoint' in v.get('analysis', '').lower()]
                    
                    if api_files:
                        # Generate API documentation (simplified version)
                        api_docs = "# API Documentation\n\nGenerated from code analysis.\n"
                        api_file = Path(self.project_path.get()) / "API_DOCUMENTATION.md"
                        with open(api_file, 'w', encoding='utf-8') as f:
                            f.write(api_docs)
                        self.progress_queue.put(("log", f"Generated: {api_file}", "SUCCESS"))
                
                self.progress_queue.put(("progress", 100))
                self.progress_queue.put(("log", "Documentation generation completed successfully! 🎉", "SUCCESS"))
                self.progress_queue.put(("status", "Completed"))
                
            finally:
                # Restore original print
                builtins.print = original_print
                
        except Exception as e:
            self.progress_queue.put(("log", f"Error during generation: {str(e)}", "ERROR"))
            self.progress_queue.put(("status", "Error"))
        finally:
            self.progress_queue.put(("finished", None))
            
    def stop_generation(self):
        """Stop the generation process."""
        self.is_running = False
        self.log_message("Stopping generation...", "INFO")
        
    def check_queue(self):
        """Check the progress queue for updates from worker thread."""
        try:
            while True:
                action, data, *extra = self.progress_queue.get_nowait()
                
                if action == "log":
                    level = extra[0] if extra else "INFO"
                    self.log_message(data, level)
                elif action == "progress":
                    self.progress_var.set(data)
                elif action == "status":
                    self.status_label.config(text=data)
                elif action == "finished":
                    self.is_running = False
                    self.generate_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    if self.progress_var.get() == 100:
                        self.status_label.config(text="Generation completed successfully")
                    else:
                        self.status_label.config(text="Generation stopped")
                        
        except queue.Empty:
            pass
        finally:
            # Schedule next check
            self.root.after(100, self.check_queue)
            
    def clear_cache(self):
        """Clear the analysis cache."""
        try:
            cache_dir = Path(self.project_path.get()) / ".rag_cache"
            if cache_dir.exists():
                import shutil
                shutil.rmtree(cache_dir)
                self.log_message("Cache cleared successfully", "SUCCESS")
            else:
                self.log_message("No cache found to clear", "INFO")
        except Exception as e:
            self.log_message(f"Error clearing cache: {str(e)}", "ERROR")
            
    def view_generated_files(self):
        """Show a dialog with generated files."""
        project_path = Path(self.project_path.get())
        generated_files = []
        
        # Check for common generated files
        files_to_check = ["README.md", "API_DOCUMENTATION.md"]
        for filename in files_to_check:
            file_path = project_path / filename
            if file_path.exists():
                generated_files.append(filename)
                
        # Check docs directory
        docs_dir = project_path / "docs"
        if docs_dir.exists():
            doc_files = list(docs_dir.glob("*.md"))
            generated_files.extend([f"docs/{f.name}" for f in doc_files])
            
        if generated_files:
            files_text = "\n".join(generated_files)
            messagebox.showinfo("Generated Files", f"Generated documentation files:\n\n{files_text}")
        else:
            messagebox.showinfo("Generated Files", "No generated documentation files found.")
            
    def open_output_folder(self):
        """Open the project folder in file explorer."""
        import subprocess
        import platform
        
        path = self.project_path.get()
        
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", path])
            else:  # Linux
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self.log_message(f"Could not open folder: {str(e)}", "ERROR")
            
    def clear_log(self):
        """Clear the output log."""
        self.output_text.delete(1.0, tk.END)
        
    def show_about(self):
        """Show about dialog."""
        about_text = """RAG Documentation Generator v1.0

A powerful tool that uses AI to automatically generate
comprehensive documentation for your codebase.

Features:
• Automatic code analysis
• README generation
• Component documentation
• API documentation
• Parallel processing
• Caching for speed
• User-friendly GUI

Built with Python, Tkinter, and your local LLM."""
        
        messagebox.showinfo("About", about_text)
        
    def run(self):
        """Start the GUI application."""
        # Initial scan of current directory
        self.scan_project_files()
        self.log_message("RAG Documentation Generator started")
        self.log_message(f"Current model: {self.current_model.get()}")
        
        # Start the main loop
        self.root.mainloop()

def main():
    """Main function to run the GUI application."""
    try:
        app = RAGDocumentationGUI()
        app.run()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start application: {str(e)}")

if __name__ == "__main__":
    main()
