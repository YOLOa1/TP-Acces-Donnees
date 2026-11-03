# TP1 Acces aux donnees et interoperabilite

Cette solution realise le TP en Python avec cinq applications graphiques Tkinter independantes et un lanceur global. Elle fonctionne sans dependance externe pour les quatre premieres applications. La cinquieme utilise `pyodbc` pour une connexion ODBC a SQL Server.

## Applications realisees

1. **Calculatrice** : addition, soustraction, multiplication et division de deux nombres.
2. **Fichier texte** : ajout, consultation, modification et suppression d'ordres de fabrication dans un fichier TSV lisible comme du texte.
3. **Fichier XML** : les memes operations dans un document XML conforme a la structure `Commandes/Commande` du sujet.
4. **Base locale** : CRUD dans SQLite avec les tables `OF_Tab`, `Piece_Tab` et `Client_Tab`.
5. **Base ODBC** : simulation locale avec SQL Server LocalDB, ou lecture configurable d'un serveur SQL Server reel.

Chaque ordre de fabrication contient une reference OF, une reference piece de 10 caracteres au maximum, une reference client de 30 caracteres au maximum, une quantite entiere positive et une date de fin au format `AAAA-MM-JJ`.

## Lancement

Python 3.10 ou plus recent est recommande.

```powershell
python init_data.py
python run_tp.py
```

Le lanceur global accepte aussi l'option `--app` :

```powershell
python run_tp.py --app calculatrice
python run_tp.py --app texte
python run_tp.py --app xml
python run_tp.py --app locale
python run_tp.py --app distante
```

Les cinq scripts `app1_calculatrice.py` a `app5_base_distante.py` peuvent egalement etre executes directement.

## Simulation ODBC locale

L'application 5 utilise par defaut l'instance SQL Server LocalDB `(localdb)\MSSQLLocalDB`. Dans l'onglet **Base ODBC** :

1. Cliquer sur **Initialiser la simulation**.
2. L'application demarre automatiquement `MSSQLLocalDB`, puis cree la base `TP_IP_Local` ainsi que `Operateur_Tab`, `Machine_Tab` et `Piece_Tab`.
3. Des donnees fictives sont inserees automatiquement.
4. Utiliser les boutons **Afficher les operateurs**, **Afficher les machines** et **Afficher les pieces**.

L'initialisation est idempotente : elle peut etre relancee sans dupliquer les donnees. Elle est volontairement refusee pour un serveur qui n'est pas LocalDB.

La simulation passe bien par le pilote ODBC, comme la connexion au serveur d'origine. Elle permet donc de tester la configuration et les requetes sans dependance au reseau de la salle.

## Serveur reel et DSN

Dans ODBC, **DSN** signifie *Data Source Name*. Il s'agit d'un nom logique qui regroupe les parametres de connexion a une source de donnees, notamment le pilote, le serveur, la base et certaines options. L'application peut ainsi se connecter en indiquant le DSN au lieu de reconstruire tous les parametres.

Pour utiliser l'application 5 :

1. Installer le pilote ODBC Microsoft pour SQL Server correspondant a l'architecture de Python.
2. Installer la dependance Python facultative avec `python -m pip install -r requirements-remote.txt`.
3. Creer un DSN utilisateur dans l'administrateur ODBC, ou saisir directement le serveur dans l'interface.
4. Renseigner le mot de passe dans l'interface. Aucun mot de passe n'est enregistre dans le projet.
5. Adapter les noms des tables si le schema du serveur differe de `Operateur_Tab`, `Machine_Tab` et `Piece_Tab`.

Les consultations sont en lecture seule. Les noms de tables sont controles avant execution et les resultats sont limites a 200 lignes. Seul le bouton d'initialisation locale cree des objets, et uniquement dans une instance LocalDB.

## Structure

```text
tp_acces_donnees/
  models.py          validation du modele OF
  repositories.py    stockage TXT, XML et SQLite
  remote.py           acces ODBC en lecture seule
  ui.py               interfaces Tkinter
tests/
  test_repositories.py
data/
  ordres.txt
  ordres.xml
  bdlocale.sqlite3
```

## Verification

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
```

