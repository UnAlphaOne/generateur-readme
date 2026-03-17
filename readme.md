# 🎨 Générateur README Pro - Éditeur WYSIWYG

<div align="center">

![Version](https://img.shields.io/badge/version-2.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8+-yellow)
![GitHub](https://img.shields.io/badge/GitHub-README-orange)

**Créez des README magnifiques pour GitHub sans écrire une ligne de Markdown !**

<img src="images/screenshot_principal.png" width="800" alt="Aperçu de l'application">


</div>

---

## ✨ Fonctionnalités

### 🎯 Éditeur WYSIWYG (What You See Is What You Get)
- **Interface visuelle intuitive** - Glissez-déposez les éléments
- **Placement libre** - Positionnez chaque élément où vous voulez
- **Redimensionnement** - Utilisez les poignées pour ajuster la taille
- **Grille magnétique** - Alignez parfaitement vos éléments
- **Undo/Redo** - Ctrl+Z / Ctrl+Y pour annuler/rétablir
- **Duplication** - Ctrl+D pour dupliquer un élément

### 🧩 Éléments disponibles
| Élément | Description | Personnalisation |
|---------|-------------|------------------|
| 🎨 **Bannière** | En-tête coloré | Texte, URL image, taille |
| 🎯 **Logo** | Cercle avec initiales | Texte, URL image, taille, couleur |
| 🎬 **GIF** | Animation | URL, taille, description |
| 📸 **Screenshot** | Capture d'écran | URL, description, taille |
| 🏷️ **Badge** | Badge de statut | Texte, couleur (bleu/vert/jaune/rouge) |
| 📝 **Texte** | Texte formaté | Police, taille, couleur, gras, italique, listes |

### 📸 Outils de capture intégrés
- **Capture de zone** - Sélectionnez une zone de l'écran avec la souris
- **Capture GIF** - Enregistrez des animations de votre application
- **Capture vidéo** - Créez des vidéos de démonstration
- **Capture fenêtre** - Capturez une fenêtre spécifique
- **Sauvegarde automatique** - Les captures sont stockées dans le dossier `images/`

### ✅ Validation GitHub
- Vérification automatique de la compatibilité
- Détection des éléments non supportés (JavaScript, iframes...)
- Score de compatibilité /100
- Avertissements pour les optimisations

### 👁️ Aperçu en temps réel
- Rendu instantané dans l'onglet "Aperçu GitHub"
- Style exact de GitHub
- Images locales affichées
- Mise à jour à chaque frappe

---

## 🚀 Installation

### Prérequis
- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)

### 1. Cloner le dépôt
```bash
git clone https://github.com/UnAlphaOne/generateur-readme.git
cd generateur-readme
```

### 2. Installer les dépendances
```bash
# Dépendances principales
pip install tkinter pillow

# Pour le rendu Markdown (aperçu)
pip install markdown markdown-extensions pymdown-extensions pygments

# Pour le rendu HTML dans l'aperçu (optionnel mais recommandé)
pip install tkinterhtml

# Pour les outils de capture
pip install pyautogui keyboard opencv-python numpy

# Pour la capture de fenêtres (Windows)
pip install pywin32
```

### 3. Lancer l'application
```bash
python generateur_readme.py
```

---

## 📖 Utilisation rapide

### 🎨 Créer votre premier README

1. **Lancez l'application**
2. **Ajoutez des éléments** en cliquant sur les boutons de la toolbar
3. **Positionnez-les** par glisser-déposer
4. **Redimensionnez** avec les poignées
5. **Personnalisez** par double-clic
6. **Générez** le Markdown avec le bouton "GÉNÉRER"
7. **Sauvegardez** votre README.md

### 📸 Capturer une image

1. Cliquez sur **"📸 Capture"** dans la toolbar
2. Sélectionnez **"🖼️ Capture PNG"**
3. Dessinez un rectangle sur l'écran
4. L'image est automatiquement sauvegardée dans `images/`
5. Confirmez pour l'ajouter directement au canvas

### 🎬 Créer un GIF animé

1. Cliquez sur **"📸 Capture"** → **"🎬 Capture GIF"**
2. Sélectionnez la zone à capturer
3. Choisissez la durée et le framerate
4. La capture démarre après 3 secondes
5. Le GIF est sauvegardé dans `images/`

---

## ⌨️ Raccourcis clavier

| Raccourci | Action |
|-----------|--------|
| `Ctrl+Z` | Annuler |
| `Ctrl+Y` | Rétablir |
| `Ctrl+D` | Dupliquer l'élément sélectionné |
| `Ctrl+A` | Tout sélectionner |
| `Suppr` | Supprimer l'élément sélectionné |
| `Ctrl+S` | Sauvegarder le projet |
| `Ctrl+O` | Ouvrir un projet |
| `Ctrl+N` | Nouveau projet |
| `Ctrl+E` | Exporter en Markdown |
| `Ctrl+Shift+S` | Capture PNG |
| `Ctrl+Shift+G` | Capture GIF |
| `Ctrl+Shift+V` | Capture vidéo |
| `Flèches` | Déplacer l'élément sélectionné |

---

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing`)
3. Commit vos changements (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Ouvrir une Pull Request

---

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🙏 Remerciements

- [Python](https://www.python.org/) - Langage de programmation
- [Tkinter](https://docs.python.org/3/library/tkinter.html) - Interface graphique
- [Markdown](https://python-markdown.github.io/) - Conversion Markdown
- [PyAutoGUI](https://pyautogui.readthedocs.io/) - Capture d'écran

---

<div align="center">

**⭐ Si ce projet vous a aidé, n'oubliez pas de mettre une étoile !**

Fait avec ❤️ par [Gérard D](https://github.com/UnAlphaOne)

</div>