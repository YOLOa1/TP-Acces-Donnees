from __future__ import annotations

import argparse
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .models import ValidationError, WorkOrder
from .remote import RemoteConfig, RemoteDatabaseClient, RemoteDatabaseError
from .repositories import (
    DuplicateReferenceError,
    SQLiteRepository,
    TextRepository,
    UnknownReferenceError,
    WorkOrderRepository,
    XmlRepository,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def configure_style(root: tk.Misc) -> None:
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
    style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))


class CalculatorView(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=24)
        self.first = tk.StringVar()
        self.second = tk.StringVar()
        self.result = tk.StringVar(value="Resultat : -")
        ttk.Label(self, text="Calculatrice simple", style="Title.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 24))
        ttk.Label(self, text="Premiere valeur").grid(row=1, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.first, width=28).grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 12), pady=(4, 16))
        ttk.Label(self, text="Deuxieme valeur").grid(row=1, column=2, sticky="w")
        ttk.Entry(self, textvariable=self.second, width=28).grid(row=2, column=2, columnspan=2, sticky="ew", pady=(4, 16))
        for column, (label, operator) in enumerate((("Addition", "+"), ("Soustraction", "-"), ("Multiplication", "*"), ("Division", "/"))):
            ttk.Button(self, text=label, command=lambda op=operator: self.calculate(op)).grid(row=3, column=column, padx=4, pady=8, sticky="ew")
        ttk.Label(self, textvariable=self.result, font=("Segoe UI", 15, "bold")).grid(row=4, column=0, columnspan=4, sticky="w", pady=(24, 0))
        for column in range(4):
            self.columnconfigure(column, weight=1)

    def calculate(self, operator: str) -> None:
        try:
            left = float(self.first.get().replace(",", "."))
            right = float(self.second.get().replace(",", "."))
            if operator == "+":
                value = left + right
            elif operator == "-":
                value = left - right
            elif operator == "*":
                value = left * right
            else:
                if right == 0:
                    raise ZeroDivisionError
                value = left / right
            self.result.set(f"Resultat : {value:g}")
        except ValueError:
            messagebox.showerror("Valeurs invalides", "Saisissez deux valeurs numeriques.", parent=self)
        except ZeroDivisionError:
            messagebox.showerror("Division impossible", "La division par zero est interdite.", parent=self)


class WorkOrderView(ttk.Frame):
    columns = ("ref_of", "ref_piece", "ref_client", "quantity", "end_date")
    headings = ("Reference OF", "Reference piece", "Reference client", "Quantite", "Date de fin")

    def __init__(self, master: tk.Misc, repository: WorkOrderRepository, title: str, storage_label: str):
        super().__init__(master, padding=18)
        self.repository = repository
        self.original_ref: str | None = None
        self.values = {name: tk.StringVar() for name in self.columns}
        ttk.Label(self, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text=storage_label).grid(row=1, column=0, sticky="w", pady=(2, 14))

        form = ttk.LabelFrame(self, text="Ordre de fabrication", style="Section.TLabelframe", padding=12)
        form.grid(row=2, column=0, sticky="ew")
        for index, (name, label) in enumerate(zip(self.columns, self.headings)):
            ttk.Label(form, text=label).grid(row=0, column=index, sticky="w", padx=4)
            entry = ttk.Entry(form, textvariable=self.values[name])
            entry.grid(row=1, column=index, sticky="ew", padx=4, pady=(4, 8))
            form.columnconfigure(index, weight=1)

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=5, sticky="w", pady=(4, 0))
        ttk.Button(actions, text="Ajouter", style="Accent.TButton", command=self.add).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Consulter", command=self.consult).pack(side="left", padx=6)
        ttk.Button(actions, text="Modifier", command=self.update).pack(side="left", padx=6)
        ttk.Button(actions, text="Supprimer", command=self.delete).pack(side="left", padx=6)
        ttk.Button(actions, text="Nouveau", command=self.clear_form).pack(side="left", padx=6)

        table_frame = ttk.Frame(self)
        table_frame.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings", selectmode="browse")
        for name, heading in zip(self.columns, self.headings):
            self.tree.heading(name, text=heading)
            self.tree.column(name, width=140, anchor="center")
        self.tree.column("ref_client", width=220, anchor="w")
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        self.refresh()

    def _order_from_form(self) -> WorkOrder:
        return WorkOrder.from_strings(*(self.values[name].get() for name in self.columns))

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for order in self.repository.list_all():
            self.tree.insert("", "end", iid=order.ref_of, values=tuple(order.as_mapping()[name] for name in self.columns))

    def clear_form(self) -> None:
        self.original_ref = None
        for variable in self.values.values():
            variable.set("")
        for item in self.tree.selection():
            self.tree.selection_remove(item)

    def _selection_changed(self, _event: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        for name, value in zip(self.columns, values):
            self.values[name].set(value)
        self.original_ref = str(values[0])

    def add(self) -> None:
        try:
            self.repository.add(self._order_from_form())
            self.refresh()
            self.clear_form()
        except (ValidationError, DuplicateReferenceError) as exc:
            messagebox.showerror("Ajout impossible", str(exc), parent=self)

    def consult(self) -> None:
        reference = self.values["ref_of"].get().strip()
        order = self.repository.get(reference)
        if order is None:
            messagebox.showinfo("Consultation", f"Aucun OF ne porte la reference {reference!r}.", parent=self)
            return
        values = order.as_mapping()
        for name in self.columns:
            self.values[name].set(values[name])
        self.original_ref = order.ref_of
        if self.tree.exists(order.ref_of):
            self.tree.selection_set(order.ref_of)
            self.tree.see(order.ref_of)

    def update(self) -> None:
        if not self.original_ref:
            messagebox.showinfo("Modification", "Selectionnez ou consultez d'abord un OF.", parent=self)
            return
        try:
            self.repository.update(self.original_ref, self._order_from_form())
            self.refresh()
            self.clear_form()
        except (ValidationError, DuplicateReferenceError, UnknownReferenceError) as exc:
            messagebox.showerror("Modification impossible", str(exc), parent=self)

    def delete(self) -> None:
        reference = self.original_ref or self.values["ref_of"].get().strip()
        if not reference:
            messagebox.showinfo("Suppression", "Selectionnez un OF.", parent=self)
            return
        if not messagebox.askyesno("Confirmer", f"Supprimer l'OF {reference} ?", parent=self):
            return
        try:
            self.repository.delete(reference)
            self.refresh()
            self.clear_form()
        except UnknownReferenceError:
            messagebox.showerror("Suppression impossible", f"L'OF {reference} n'existe pas.", parent=self)


class RemoteDatabaseView(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=18)
        ttk.Label(self, text="Base de donnees ODBC", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="Simulation locale par defaut, ou connexion a un serveur SQL Server reel").grid(row=1, column=0, sticky="w", pady=(2, 14))
        local = RemoteConfig.local_simulation()
        self.fields = {
            "dsn": tk.StringVar(value=local.dsn),
            "driver": tk.StringVar(value=local.driver),
            "server": tk.StringVar(value=local.server),
            "database": tk.StringVar(value=local.database),
            "user": tk.StringVar(value=local.user),
            "password": tk.StringVar(value=local.password),
        }
        config = ttk.LabelFrame(self, text="Connexion", style="Section.TLabelframe", padding=12)
        config.grid(row=2, column=0, sticky="ew")
        labels = (("dsn", "DSN (prioritaire)"), ("driver", "Pilote"), ("server", "Serveur"), ("database", "Base"), ("user", "Utilisateur"), ("password", "Mot de passe"))
        for index, (name, label) in enumerate(labels):
            ttk.Label(config, text=label).grid(row=0, column=index, sticky="w", padx=4)
            ttk.Entry(config, textvariable=self.fields[name], show="*" if name == "password" else "").grid(row=1, column=index, sticky="ew", padx=4, pady=(4, 0))
            config.columnconfigure(index, weight=1)
        connection_actions = ttk.Frame(config)
        connection_actions.grid(row=2, column=0, columnspan=6, sticky="w", pady=(10, 0))
        ttk.Button(connection_actions, text="Utiliser la simulation locale", command=self.use_local_simulation).pack(side="left", padx=(0, 6))
        ttk.Button(connection_actions, text="Initialiser la simulation", style="Accent.TButton", command=self.initialize_simulation).pack(side="left", padx=6)
        ttk.Button(connection_actions, text="Tester la connexion", command=self.test_connection).pack(side="left", padx=6)

        datasets = ttk.LabelFrame(self, text="Tables a consulter", style="Section.TLabelframe", padding=12)
        datasets.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.tables = {
            "Operateurs": tk.StringVar(value="Operateur_Tab"),
            "Machines": tk.StringVar(value="Machine_Tab"),
            "Pieces": tk.StringVar(value="Piece_Tab"),
        }
        for column, (label, variable) in enumerate(self.tables.items()):
            ttk.Label(datasets, text=label).grid(row=0, column=column, sticky="w", padx=4)
            ttk.Entry(datasets, textvariable=variable).grid(row=1, column=column, sticky="ew", padx=4, pady=4)
            ttk.Button(datasets, text=f"Afficher {label.lower()}", command=lambda l=label, v=variable: self.load_table(l, v.get())).grid(row=2, column=column, sticky="ew", padx=4, pady=(4, 0))
            datasets.columnconfigure(column, weight=1)

        table_frame = ttk.Frame(self)
        table_frame.grid(row=4, column=0, sticky="nsew", pady=(14, 0))
        self.tree = ttk.Treeview(table_frame, show="headings")
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.status = tk.StringVar(value="Simulation locale selectionnee. Cliquez sur Initialiser la simulation.")
        ttk.Label(self, textvariable=self.status).grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

    def _config(self) -> RemoteConfig:
        return RemoteConfig(**{name: variable.get() for name, variable in self.fields.items()})

    def use_local_simulation(self) -> None:
        local = RemoteConfig.local_simulation()
        for name, variable in self.fields.items():
            variable.set(getattr(local, name))
        self.status.set("Simulation locale selectionnee. Initialisez-la si necessaire.")

    def initialize_simulation(self) -> None:
        self.use_local_simulation()
        self.status.set("Creation de TP_IP_Local et des donnees de demonstration...")
        self.update_idletasks()
        try:
            counts = RemoteDatabaseClient(self._config()).initialize_local_simulation()
        except RemoteDatabaseError as exc:
            self.status.set("Echec de l'initialisation locale.")
            messagebox.showerror("Simulation locale", str(exc), parent=self)
            return
        self.status.set(
            "Simulation prete : "
            f"{counts['operateurs']} operateur(s), {counts['machines']} machine(s), "
            f"{counts['pieces']} piece(s)."
        )
        messagebox.showinfo("Simulation locale", "La base TP_IP_Local est prete.", parent=self)

    def test_connection(self) -> None:
        self.status.set("Test de la connexion ODBC...")
        self.update_idletasks()
        try:
            server, database = RemoteDatabaseClient(self._config()).test_connection()
        except RemoteDatabaseError as exc:
            self.status.set("Echec du test de connexion.")
            messagebox.showerror("Connexion ODBC", str(exc), parent=self)
            return
        self.status.set(f"Connexion reussie : serveur {server}, base {database}.")
        messagebox.showinfo("Connexion ODBC", f"Connexion reussie a {database}.", parent=self)

    def load_table(self, label: str, table: str) -> None:
        config = self._config()
        self.status.set(f"Connexion et lecture de {label.lower()}...")
        self.update_idletasks()
        try:
            columns, rows = RemoteDatabaseClient(config).fetch_table(table)
        except RemoteDatabaseError as exc:
            self.status.set("Echec de la lecture distante.")
            messagebox.showerror("Base distante", str(exc), parent=self)
            return
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=columns)
        for column in columns:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=150, anchor="w")
        for row in rows:
            self.tree.insert("", "end", values=tuple("" if value is None else value for value in row))
        self.status.set(f"{len(rows)} ligne(s) affichee(s) depuis {table}.")


def _repository(kind: str) -> WorkOrderRepository:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if kind == "texte":
        return TextRepository(DATA_DIR / "ordres.txt")
    if kind == "xml":
        return XmlRepository(DATA_DIR / "ordres.xml")
    return SQLiteRepository(DATA_DIR / "bdlocale.sqlite3")


def create_view(master: tk.Misc, app: str) -> ttk.Frame:
    if app == "calculatrice":
        return CalculatorView(master)
    if app == "texte":
        return WorkOrderView(master, _repository("texte"), "Ordres de fabrication - fichier texte", str(DATA_DIR / "ordres.txt"))
    if app == "xml":
        return WorkOrderView(master, _repository("xml"), "Ordres de fabrication - fichier XML", str(DATA_DIR / "ordres.xml"))
    if app == "locale":
        return WorkOrderView(master, _repository("locale"), "Ordres de fabrication - base locale", str(DATA_DIR / "bdlocale.sqlite3"))
    if app == "distante":
        return RemoteDatabaseView(master)
    raise ValueError(app)


def run_single(app: str) -> None:
    root = tk.Tk()
    root.title(f"TP1 - {app.capitalize()}")
    root.geometry("1120x720")
    root.minsize(860, 560)
    configure_style(root)
    view = create_view(root, app)
    view.pack(fill="both", expand=True)
    footer = ttk.Frame(root, padding=(12, 4, 12, 10))
    footer.pack(fill="x")
    ttk.Button(footer, text="Quitter", command=root.destroy).pack(side="right")
    root.mainloop()


def run_all() -> None:
    root = tk.Tk()
    root.title("TP1 - Acces aux donnees et interoperabilite")
    root.geometry("1220x780")
    root.minsize(920, 620)
    configure_style(root)
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    for app, label in (("calculatrice", "1 Calculatrice"), ("texte", "2 Fichier texte"), ("xml", "3 Fichier XML"), ("locale", "4 Base locale"), ("distante", "5 Base distante")):
        view = create_view(notebook, app)
        notebook.add(view, text=label)
    footer = ttk.Frame(root, padding=(12, 0, 12, 10))
    footer.pack(fill="x")
    ttk.Button(footer, text="Quitter", command=root.destroy).pack(side="right")
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="TP1 Acces aux donnees")
    parser.add_argument("--app", choices=("tout", "calculatrice", "texte", "xml", "locale", "distante"), default="tout")
    args = parser.parse_args()
    run_all() if args.app == "tout" else run_single(args.app)


if __name__ == "__main__":
    main()

