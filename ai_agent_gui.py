import os
import sys
import threading
import subprocess
import json
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pathlib import Path

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# config file to persist last selection and options
CONFIG_FILE = ".ai_agent_gui_config.json"


class AIAgentGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Agent AI — Interface de test")
        self.geometry("900x600")

        # Left frame: controls
        self.left_frame = ctk.CTkFrame(master=self, width=320)
        self.left_frame.pack(side="left", fill="y", padx=12, pady=12)

        self.path_var = ctk.StringVar()
        self.merge_mode_var = tk.StringVar(value="merge")  # 'merge' or 'individual'
        self.showjson_var = ctk.BooleanVar(value=False)
        self.merge_name_var = ctk.StringVar(value="resultat.json")
        self.selected_paths = []

        ctk.CTkLabel(master=self.left_frame, text="Dossier / Fichier à analyser").pack(pady=(6, 2))
        path_entry = ctk.CTkEntry(master=self.left_frame, textvariable=self.path_var, width=260)
        path_entry.pack(pady=(0, 8))

        ctk.CTkButton(master=self.left_frame, text="Parcourir", command=self.browse).pack(pady=4)

        ctk.CTkLabel(master=self.left_frame, text="Options").pack(pady=(12, 6))
        ctk.CTkLabel(master=self.left_frame, text="Mode de sortie:").pack(anchor="w", padx=6)
        self.mode_menu = ctk.CTkOptionMenu(master=self.left_frame, values=["Fusionner (un fichier)", "Individuel (un par document)"], command=self._on_mode_change)
        self.mode_menu.set("Fusionner (un fichier)")
        self.mode_menu.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkLabel(master=self.left_frame, text="Nom du fichier fusionné:").pack(pady=(8, 0))
        ctk.CTkEntry(master=self.left_frame, textvariable=self.merge_name_var).pack(pady=(0, 6), padx=6)
        ctk.CTkCheckBox(master=self.left_frame, text="Afficher le JSON complet après analyse", variable=self.showjson_var).pack(anchor="w", padx=6)

        self.run_btn = ctk.CTkButton(master=self.left_frame, text="Exécuter l'analyse", command=self.start_analysis)
        self.run_btn.pack(pady=(12, 6))

        self.progress = ctk.CTkProgressBar(master=self.left_frame, orientation="horizontal")
        self.progress.pack(fill="x", padx=6, pady=(6, 0))

        # Right frame: results and logs
        self.right_frame = ctk.CTkFrame(master=self)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=12, pady=12)

        top_frame = ctk.CTkFrame(master=self.right_frame)
        top_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(master=top_frame, text="Fichiers JSON générés").pack(anchor="w")

        self.listbox = tk.Listbox(top_frame, height=6)
        self.listbox.pack(fill="x", pady=6)
        self.listbox.bind("<<ListboxSelect>>", self.on_select_json)

        btn_frame = ctk.CTkFrame(master=self.right_frame)
        btn_frame.pack(fill="x")
        ctk.CTkButton(master=btn_frame, text="Ouvrir dossier JSON", command=self.open_json_folder).pack(side="left", padx=6)
        ctk.CTkButton(master=btn_frame, text="Recharger la liste", command=self.scan_jsons).pack(side="left", padx=6)
        ctk.CTkButton(master=btn_frame, text="Sauvegarder sélection", command=self.save_selected_json).pack(side="left", padx=6)

        ctk.CTkLabel(master=self.right_frame, text="Aperçu / Logs").pack(anchor="w", pady=(12, 0))
        self.text = tk.Text(self.right_frame, wrap="none")
        self.text.pack(fill="both", expand=True, pady=(6, 0))

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # state
        self.running = False
        self.process = None

        # initial scan
        self.scan_jsons()

    def browse(self):
        # ask whether user wants a folder or files
        choose_folder = messagebox.askyesno("Choix", "Sélectionner un dossier? (Oui)\nSélectionner des fichiers (PDF/images)? (Non)")
        if choose_folder:
            path = filedialog.askdirectory(initialdir=os.getcwd())
            if path:
                self.selected_paths = [path]
        else:
            files = filedialog.askopenfilenames(initialdir=os.getcwd(), filetypes=[("PDF", "*.pdf"), ("Images", "*.png;*.jpg;*.jpeg;*.tiff;*.tif" )])
            if files:
                # filter out any JSONs just in case
                files = [f for f in files if not f.lower().endswith('.json')]
                self.selected_paths = list(files)

        # update entry display and scan jsons from selected folders
        if self.selected_paths:
            self.path_var.set(self._display_selected())
        self.scan_jsons()

    def start_analysis(self):
        if not self.selected_paths:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un dossier ou des fichiers (PDF/images) à analyser.")
            return

        if self.running:
            messagebox.showinfo("Info", "Une analyse est déjà en cours.")
            return

        # depending on selection and mode, run Factor_AI appropriately
        mode = 'merge' if self.mode_menu.get().startswith('Fusionner') else 'individual'

        thread = threading.Thread(target=self._run_for_selection, args=(mode,), daemon=True)
        thread.start()

    def _on_mode_change(self, value):
        # map option menu to internal mode
        if value.startswith('Fusionner'):
            self.merge_mode_var.set('merge')
        else:
            self.merge_mode_var.set('individual')

    def _run_subprocess(self, cmd):
        self.running = True
        self.run_btn.configure(state="disabled")
        self.progress.start()
        self._append_text(f"Lancement: {' '.join(cmd)}\n")

        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        except Exception as e:
            self._append_text(f"Erreur lancement: {e}\n")
            self.running = False
            self.progress.stop()
            self.run_btn.configure(state="normal")
            return

        # read output
        for line in self.process.stdout:
            self._append_text(line)

        self.process.wait()
        rc = self.process.returncode
        self._append_text(f"Process terminé (code {rc})\n")

        # refresh json list
        self.scan_jsons()

        self.running = False
        self.progress.stop()
        self.run_btn.configure(state="normal")

    def _run_for_selection(self, mode):
        # mode: 'merge' or 'individual'
        self.running = True
        self.run_btn.configure(state="disabled")
        self.progress.start()
        start_time = time.time()
        generated = []

        # helper to run on a single path
        def run_path(p, merge_flag=False, merge_name=None):
            cmd = [sys.executable, "Factor_AI.py", p]
            if merge_flag:
                cmd.append('--merge')
                if merge_name:
                    cmd.extend(['--merge-name', merge_name])
            if self.showjson_var.get():
                cmd.append('--show-json')
            self._append_text(f"Lancement: {' '.join(cmd)}\n")
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            except Exception as e:
                self._append_text(f"Erreur lancement: {e}\n")
                return None
            for line in proc.stdout:
                self._append_text(line)
            proc.wait()
            return proc.returncode

        # If single selection and it's a directory, prefer passing directory directly
        if len(self.selected_paths) == 1 and os.path.isdir(self.selected_paths[0]):
            p = self.selected_paths[0]
            if mode == 'merge':
                rc = run_path(p, merge_flag=True, merge_name=self.merge_name_var.get().strip())
            else:
                rc = run_path(p, merge_flag=False)
            generated.append(p)
        else:
            # multiple files or single file: run per-file
            for p in self.selected_paths:
                rc = run_path(p, merge_flag=False)
                generated.append(p)

            # if user requested merge and selected files, merge generated JSONs ourselves
            if mode == 'merge':
                try:
                    merge_name = self.merge_name_var.get().strip() or 'resultat.json'
                    merged_path = self._merge_generated_jsons(generated, merge_name)
                    self._append_text(f"💾  JSON fusionné → {merged_path}\n")
                except Exception as e:
                    self._append_text(f"Erreur durant la fusion: {e}\n")

        self.scan_jsons()
        self.running = False
        self.progress.stop()
        self.run_btn.configure(state="normal")
        # persist config
        self.save_config()

    def _merge_generated_jsons(self, paths, merge_name):
        # collect JSON files generated for each source path and merge into one
        merged = []
        for p in paths:
            folder = os.path.dirname(p) if os.path.isfile(p) else p
            base = os.path.splitext(os.path.basename(p))[0]
            # find json files starting with base
            for f in os.listdir(folder):
                if f.lower().endswith('.json') and f.startswith(base):
                    try:
                        with open(os.path.join(folder, f), 'r', encoding='utf-8') as fh:
                            data = json.load(fh)
                            if isinstance(data, list):
                                merged.extend(data)
                            else:
                                merged.append(data)
                    except Exception:
                        continue
        # write merged
        out_folder = os.path.dirname(paths[0]) if os.path.isfile(paths[0]) else paths[0]
        out_path = os.path.join(out_folder, merge_name)
        with open(out_path, 'w', encoding='utf-8') as out:
            json.dump(merged, out, ensure_ascii=False, indent=2)
        return out_path

    def _append_text(self, s):
        def append():
            self.text.insert("end", s)
            self.text.see("end")
        self.text.after(0, append)

    def scan_jsons(self):
        # scan JSONs in selected folders or current working dir
        folders = set()
        if self.selected_paths:
            for p in self.selected_paths:
                if os.path.isdir(p):
                    folders.add(p)
                else:
                    folders.add(os.path.dirname(p))
        else:
            folders.add(os.getcwd())

        self.listbox.delete(0, tk.END)
        for folder in sorted(folders):
            try:
                files = [f for f in os.listdir(folder) if f.lower().endswith('.json')]
            except Exception:
                files = []
            for f in sorted(files):
                self.listbox.insert(tk.END, os.path.join(folder, f))

    def open_json_folder(self):
        folder = self.path_var.get().strip() or os.getcwd()
        if os.path.isfile(folder):
            folder = os.path.dirname(folder)
        try:
            if sys.platform.startswith('win'):
                os.startfile(folder)
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le dossier: {e}")

    def on_select_json(self, evt):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = self.listbox.get(sel[0])
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.text.delete('1.0', tk.END)
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            self.text.insert('1.0', pretty)
        except Exception as e:
            self.text.delete('1.0', tk.END)
            self.text.insert('1.0', f"Erreur lecture JSON: {e}")

    def save_selected_json(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Aucune sélection.")
            return
        path = self.listbox.get(sel[0])
        dest = filedialog.asksaveasfilename(defaultextension='.json', initialfile=os.path.basename(path))
        if dest:
            try:
                with open(path, 'rb') as src, open(dest, 'wb') as dst:
                    dst.write(src.read())
                messagebox.showinfo("Succès", f"Fichier sauvegardé: {dest}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de sauvegarder: {e}")

    def on_close(self):
        if self.running and self.process:
            if not messagebox.askyesno("Quitter", "Une analyse est en cours. Voulez-vous forcer la fermeture ?"):
                return
            try:
                self.process.kill()
            except Exception:
                pass
        # persist config
        try:
            self.save_config()
        except Exception:
            pass
        self.destroy()

    def _display_selected(self):
        if not self.selected_paths:
            return ''
        if len(self.selected_paths) == 1:
            return self.selected_paths[0]
        return f"{len(self.selected_paths)} éléments sélectionnés"

    def load_config(self):
        try:
            cfg = Path(CONFIG_FILE)
            if cfg.exists():
                data = json.loads(cfg.read_text(encoding='utf-8'))
                self.selected_paths = data.get('selected_paths', [])
                mode = data.get('mode', 'merge')
                if mode == 'merge':
                    self.mode_menu.set('Fusionner (un fichier)')
                else:
                    self.mode_menu.set('Individuel (un par document)')
                self.merge_name_var.set(data.get('merge_name', self.merge_name_var.get()))
                self.showjson_var.set(data.get('showjson', self.showjson_var.get()))
                if self.selected_paths:
                    self.path_var.set(self._display_selected())
        except Exception:
            pass

    def save_config(self):
        data = {
            'selected_paths': self.selected_paths,
            'mode': 'merge' if self.mode_menu.get().startswith('Fusionner') else 'individual',
            'merge_name': self.merge_name_var.get().strip(),
            'showjson': bool(self.showjson_var.get())
        }
        try:
            Path(CONFIG_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass


def main():
    app = AIAgentGUI()
    # load persisted configuration
    app.load_config()
    app.mainloop()


if __name__ == '__main__':
    main()
