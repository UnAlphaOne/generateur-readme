import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, Menu
import json
import re
from pathlib import Path
import pyautogui
import keyboard
from PIL import Image, ImageGrab
import io
import time
import threading
from datetime import datetime
import cv2
import numpy as np
import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.toc import TocExtension
from markdown.extensions.nl2br import Nl2BrExtension
import webbrowser
import tempfile
import os

class Historique:
    """Gère l'historique pour undo/redo"""
    def __init__(self, max_size=50):
        self.states = []
        self.current = -1
        self.max_size = max_size
    
    def push(self, state):
        """Ajoute un état"""
        # Supprimer les états après current (pour redo)
        self.states = self.states[:self.current + 1]
        
        # Ajouter nouveau état
        self.states.append(state)
        if len(self.states) > self.max_size:
            self.states.pop(0)
        
        self.current = len(self.states) - 1
    
    def undo(self):
        """Retourne l'état précédent"""
        if self.current > 0:
            self.current -= 1
            return self.states[self.current]
        return None
    
    def redo(self):
        """Retourne l'état suivant"""
        if self.current < len(self.states) - 1:
            self.current += 1
            return self.states[self.current]
        return None
    
    def can_undo(self):
        return self.current > 0
    
    def can_redo(self):
        return self.current < len(self.states) - 1

class ValidateurGitHub:
    """Valide la compatibilité GitHub"""
    
    HTML_INTERDIT = [
        ('<script', 'JavaScript interdit'),
        ('<style', 'CSS interne interdit'),
        ('<iframe', 'Iframe interdit'),
        ('position:', 'Positionnement CSS interdit'),
        ('transform:', 'Transformations CSS interdites'),
        ('z-index:', 'Z-index interdit'),
        ('onclick=', 'Événements JavaScript interdits'),
        ('onload=', 'Événements JavaScript interdits'),
    ]
    
    HTML_ACCEPTABLE = [
        '<div', '<img', '<br', '<p', '<h1', '<h2', '<h3',
        '<a', '<b', '<i', '<strong', '<em', '<ul', '<ol', '<li',
        '<table', '<tr', '<td', '<th', '<thead', '<tbody',
        '<details', '<summary', '<blockquote'
    ]
    
    @classmethod
    def valider(cls, markdown):
        """Valide le markdown pour GitHub"""
        erreurs = []
        avertissements = []
        
        # Vérifier HTML interdit
        for pattern, message in cls.HTML_INTERDIT:
            if pattern.lower() in markdown.lower():
                erreurs.append(f"❌ {message}: `{pattern}`")
        
        # Vérifier les attributs style
        style_matches = re.findall(r'style\s*=\s*["\']([^"\']+)["\']', markdown, re.IGNORECASE)
        for style in style_matches:
            styles_interdits = ['position', 'transform', 'z-index', 'animation', 'transition']
            for s in styles_interdits:
                if s in style.lower():
                    erreurs.append(f"❌ Style CSS interdit: `{s}`")
        
        # Vérifier les URLs d'images
        img_urls = re.findall(r'src\s*=\s*["\']([^"\']+)["\']', markdown)
        for url in img_urls:
            if not url.startswith(('http://', 'https://', './', '../', '/')):
                avertissements.append(f"⚠️ URL relative potentiellement invalide: `{url[:30]}...`")
            if url.endswith(('.mp4', '.webm', '.mov')):
                erreurs.append(f"❌ Vidéo non supportée: `{url}` (utilisez GIF à la place)")
        
        # Vérifier les iframes YouTube
        if 'youtube.com/embed' in markdown or 'youtube.com/watch' in markdown:
            if '<iframe' in markdown:
                erreurs.append("❌ Iframe YouTube interdit (utilisez une image avec lien)")
        
        # Vérifier la taille des GIFs (avertissement si URL externe)
        gif_urls = re.findall(r'src\s*=\s*["\']([^"\']+\.gif)["\']', markdown, re.IGNORECASE)
        if len(gif_urls) > 3:
            avertissements.append(f"⚠️ {len(gif_urls)} GIFs détectés - risque de lenteur")
        
        return {
            'valide': len(erreurs) == 0,
            'erreurs': erreurs,
            'avertissements': avertissements,
            'score': max(0, 100 - len(erreurs) * 20 - len(avertissements) * 5)
        }

class ElementCanvas:
    """Représente un élément sur le canvas"""
    def __init__(self, canvas, type_elem, x, y, **kwargs):
        self.canvas = canvas
        self.type = type_elem
        self.x = x
        self.y = y
        self.kwargs = kwargs
        
        self.items = []
        self.handles = []
        self.selected = False
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        
        self.creer()
    
    def creer(self):
        """Crée l'élément graphique"""
        if self.type == 'banniere':
            self.creer_banniere()
        elif self.type == 'logo':
            self.creer_logo()
        elif self.type == 'gif':
            self.creer_gif()
        elif self.type == 'screenshot':
            self.creer_screenshot()
        elif self.type == 'badge':
            self.creer_badge()
        elif self.type == 'texte':
            self.creer_texte()
        
        for item_id in self.items:
            self.canvas.tag_bind(item_id, '<Button-1>', self.on_click)
            self.canvas.tag_bind(item_id, '<B1-Motion>', self.on_drag)
            self.canvas.tag_bind(item_id, '<ButtonRelease-1>', self.on_release)
            self.canvas.tag_bind(item_id, '<Double-Button-1>', self.on_double_click)
    
    def creer_banniere(self):
        w, h = 700, 200
        self.w, self.h = w, h
        
        rect = self.canvas.create_rectangle(self.x, self.y, self.x+w, self.y+h,
                                           fill='#238636', outline='#2ea043', width=2)
        text = self.canvas.create_text(self.x + w//2, self.y + h//2,
                                      text=self.kwargs.get('texte', 'Mon Projet'),
                                      font=('Segoe UI', 24, 'bold'), fill='white')
        self.items = [rect, text]
        self.main_item = rect
        self.text_item = text
    
    def creer_logo(self):
        r = 75
        self.r = r
        
        cercle = self.canvas.create_oval(self.x-r, self.y-r, self.x+r, self.y+r,
                                        fill='#1f6feb', outline='#58a6ff', width=3)
        text = self.canvas.create_text(self.x, self.y,
                                      text=self.kwargs.get('texte', 'LO')[:2].upper(),
                                      font=('Segoe UI', 32, 'bold'), fill='white')
        self.items = [cercle, text]
        self.main_item = cercle
        self.text_item = text
    
    def creer_gif(self):
        w, h = 400, 300
        self.w, self.h = w, h
        
        rect = self.canvas.create_rectangle(self.x, self.y, self.x+w, self.y+h,
                                           fill='#161b22', outline='#30363d', width=2)
        barre = self.canvas.create_rectangle(self.x, self.y, self.x+w, self.y+25,
                                            fill='#21262d', outline='#30363d')
        btn1 = self.canvas.create_oval(self.x+10, self.y+8, self.x+18, self.y+16,
                                      fill='#ff5f56', outline='#e0443e')
        btn2 = self.canvas.create_oval(self.x+22, self.y+8, self.x+30, self.y+16,
                                      fill='#ffbd2e', outline='#dea123')
        btn3 = self.canvas.create_oval(self.x+34, self.y+8, self.x+42, self.y+16,
                                      fill='#27c93f', outline='#1aab29')
        text = self.canvas.create_text(self.x + w//2, self.y + h//2,
                                      text="🎬 GIF de démonstration\n(cliquez pour configurer)",
                                      font=('Segoe UI', 12), fill='#8b949e', justify='center')
        
        self.items = [rect, barre, btn1, btn2, btn3, text]
        self.main_item = rect
        self.text_item = text
    
    def creer_screenshot(self):
        w, h = 330, 220
        self.w, self.h = w, h
        
        rect = self.canvas.create_rectangle(self.x, self.y, self.x+w, self.y+h,
                                           fill='#21262d', outline='#30363d', width=2)
        text = self.canvas.create_text(self.x + w//2, self.y + h//2,
                                      text=f"📸 {self.kwargs.get('description', 'Screenshot')}\n(cliquez pour configurer)",
                                      font=('Segoe UI', 11), fill='#8b949e', justify='center')
        
        self.items = [rect, text]
        self.main_item = rect
        self.text_item = text
    
    def creer_badge(self):
        w, h = 120, 30
        self.w, self.h = w, h
        
        couleurs = {'blue': '#007ec6', 'green': '#4c1', 'yellow': '#dfb317', 'red': '#e05d44'}
        couleur = couleurs.get(self.kwargs.get('couleur', 'blue'), '#007ec6')
        
        rect = self.canvas.create_rectangle(self.x, self.y, self.x+w, self.y+h,
                                           fill=couleur, outline='')
        text = self.canvas.create_text(self.x + w//2, self.y + h//2,
                                      text=self.kwargs.get('texte', 'badge'),
                                      font=('Segoe UI', 10, 'bold'), fill='white')
        
        self.items = [rect, text]
        self.main_item = rect
        self.text_item = text
    
    def creer_texte(self):
        """Crée un élément texte redimensionnable"""
        # Récupérer les paramètres
        texte = self.kwargs.get('texte', 'Texte personnalisé')
        font_family = self.kwargs.get('font_family', 'Segoe UI')
        font_size = self.kwargs.get('font_size', 12)
        couleur = self.kwargs.get('couleur', '#f0f6fc')
        
        # Si on a une taille personnalisée stockée, l'utiliser
        if hasattr(self, 'custom_width') and hasattr(self, 'custom_height'):
            largeur = self.custom_width
            hauteur = self.custom_height
        else:
            largeur = 400
            hauteur = 100
        
        # Créer le texte avec un fond pour faciliter la sélection
        font = (font_family, font_size)
        
        # Créer d'abord un rectangle pour le fond (invisible mais pour la sélection)
        rect_fond = self.canvas.create_rectangle(
            self.x, self.y, self.x + largeur, self.y + hauteur,
            fill='#1f2429', outline='', stipple='gray50', tags='text_bg'
        )
        
        # Créer le texte
        text = self.canvas.create_text(
            self.x + 10, self.y + 10,  # Marge de 10 pixels
            text=texte,
            font=font,
            fill=couleur,
            anchor='nw',  # Ancrage en haut à gauche
            width=largeur - 20  # Largeur max avec marges
        )
        
        # Ajuster la hauteur en fonction du contenu
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox(text)
        if bbox:
            hauteur = max(hauteur, bbox[3] - bbox[1] + 20)
            largeur = max(largeur, bbox[2] - bbox[0] + 20)
        
        # Mettre à jour le rectangle de fond
        self.canvas.coords(rect_fond, self.x, self.y, self.x + largeur, self.y + hauteur)
        
        # Rectangle de sélection (visible seulement quand sélectionné)
        rect_selection = self.canvas.create_rectangle(
            self.x, self.y, self.x + largeur, self.y + hauteur,
            fill='', outline='#58a6ff', width=1, dash=(4, 2), tags='text_border',
            state='hidden'  # Caché par défaut
        )
        
        # Lier les événements de drag à tous les éléments
        for item in [rect_fond, text, rect_selection]:
            self.canvas.tag_bind(item, '<Button-1>', self.on_click)
            self.canvas.tag_bind(item, '<B1-Motion>', self.on_drag)
            self.canvas.tag_bind(item, '<ButtonRelease-1>', self.on_release)
            self.canvas.tag_bind(item, '<Double-Button-1>', self.on_double_click)
        
        self.items = [rect_fond, text, rect_selection]
        self.main_item = rect_fond  # Le fond est l'élément principal pour le déplacement
        self.text_item = text
        self.bbox_item = rect_selection
        self.w = largeur
        self.h = hauteur
        self.custom_width = largeur
        self.custom_height = hauteur
    
    def on_click(self, event):
        if self.resizing:
            return
        
        # Vérifier si on clique sur une poignée
        items = self.canvas.find_closest(event.x, event.y)
        if items:
            tags = self.canvas.gettags(items[0])
            if 'handle' in tags:
                return
        
        # Sauvegarder l'état pour undo
        self.canvas.sauver_etat()
        
        # Désélectionner tout d'abord
        self.canvas.deselectionner_tout()
        
        # Sélectionner cet élément
        self.canvas.element_selectionne = self
        self.selectionner()
        
        # Forcer la mise à jour immédiate
        self.canvas.update_idletasks()
        
        self.dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.start_x = self.x
        self.start_y = self.y
    
    def on_drag(self, event):
        if not self.dragging or self.resizing:
            return
        
        new_x = self.start_x + (event.x - self.drag_start_x)
        new_y = self.start_y + (event.y - self.drag_start_y)
        
        # Grille magnétique (snap to grid 50px)
        if getattr(self.canvas, 'magnetisme', False):
            new_x = round(new_x / 50) * 50
            new_y = round(new_y / 50) * 50
        
        margin = 10
        canvas_width = 1200  # Nouvelle largeur
        canvas_height = 900  # Nouvelle hauteur
        
        if self.type == 'logo':
            new_x = max(self.r + margin, min(canvas_width - self.r - margin, new_x))
            new_y = max(self.r + margin, min(canvas_height - self.r - margin, new_y))
        else:
            w = getattr(self, 'w', 100)
            h = getattr(self, 'h', 50)
            new_x = max(margin, min(canvas_width - w - margin, new_x))
            new_y = max(margin, min(canvas_height - h - margin, new_y))
        
        dx = new_x - self.x
        dy = new_y - self.y
        
        for item in self.items:
            self.canvas.move(item, dx, dy)
        for handle in self.handles:
            self.canvas.move(handle, dx, dy)
        
        self.x = new_x
        self.y = new_y
    
    def on_release(self, event):
        self.dragging = False
        self.resizing = False
    
    def on_double_click(self, event):
        self.editer()
    
    def selectionner(self):
        self.selected = True
        
        # Mettre en surbrillance l'élément
        if self.type == 'logo':
            self.canvas.itemconfig(self.main_item, outline='#f78166', width=4)
        elif self.type == 'badge':
            self.canvas.itemconfig(self.main_item, outline='#f78166', width=2)
        elif self.type == 'texte':
            if len(self.items) >= 3:
                self.canvas.itemconfig(self.items[2], state='normal', outline='#f78166', width=2)
                self.canvas.itemconfig(self.items[0], stipple='gray25')
        else:
            self.canvas.itemconfig(self.main_item, outline='#f78166', width=3)
        
        # Créer les poignées
        self.creer_poignees()
        
        # Forcer la mise à jour
        self.canvas.update_idletasks()

    def deselectionner(self):
        self.selected = False
        
        for handle in self.handles:
            self.canvas.delete(handle)
        self.handles = []
        
        if self.type == 'logo':
            self.canvas.itemconfig(self.main_item, outline='#58a6ff', width=3)
        elif self.type == 'badge':
            self.canvas.itemconfig(self.main_item, outline='', width=0)
        elif self.type == 'texte':
            if len(self.items) >= 3:
                # Cacher la bordure
                self.canvas.itemconfig(self.items[2], state='hidden')
                # Remettre le fond normal
                self.canvas.itemconfig(self.items[0], stipple='')
        else:
            couleurs = {'banniere': '#2ea043', 'gif': '#30363d', 'screenshot': '#30363d'}
            self.canvas.itemconfig(self.main_item, 
                                 outline=couleurs.get(self.type, '#30363d'), width=2)
    
    def creer_poignees(self):
        """Crée les poignées de redimensionnement immédiatement visibles"""
        # Supprimer les anciennes poignées
        for handle in self.handles:
            self.canvas.delete(handle)
        self.handles = []
        
        # Poignées plus grandes et plus visibles
        handle_size = 5  # Encore plus grand
        
        if self.type == 'logo':
            r = self.r
            positions = [
                (self.x, self.y - r, 'n'), (self.x + r, self.y, 'e'),
                (self.x, self.y + r, 's'), (self.x - r, self.y, 'w')
            ]
        else:
            w, h = getattr(self, 'w', 100), getattr(self, 'h', 100)
            positions = [
                (self.x, self.y, 'nw'), (self.x + w, self.y, 'ne'),
                (self.x, self.y + h, 'sw'), (self.x + w, self.y + h, 'se')
            ]
        
        for hx, hy, direction in positions:
            # Poignée carrée avec couleur vive
            handle_id = self.canvas.create_rectangle(
                hx-handle_size, hy-handle_size, 
                hx+handle_size, hy+handle_size,
                fill='#f78166', outline='white', width=3,
                tags=('handle',)
            )
            self.handles.append(handle_id)
            
            def make_callback(d):
                return lambda e: self.start_resize(e, d)
            
            # Bind des événements
            self.canvas.tag_bind(handle_id, '<ButtonPress-1>', make_callback(direction))
            self.canvas.tag_bind(handle_id, '<B1-Motion>', self.do_resize)
            self.canvas.tag_bind(handle_id, '<ButtonRelease-1>', self.stop_resize)
            
            # Changer le curseur au survol
            self.canvas.tag_bind(handle_id, '<Enter>', 
                                lambda e: self.canvas.config(cursor='sizing'))
            self.canvas.tag_bind(handle_id, '<Leave>', 
                                lambda e: self.canvas.config(cursor=''))
        
        # S'assurer que les poignées sont au premier plan
        for handle in self.handles:
            self.canvas.tag_raise(handle)

    def show_handle_tooltip(self, event, direction):
        """Affiche une info-bulle pour la direction de redimensionnement"""
        self.canvas.tooltip_text = self.canvas.create_text(
            event.x, event.y - 20,
            text=f"Redimensionner: {direction}",
            fill='white', font=('Segoe UI', 8),
            tags='tooltip'
        )

    def hide_handle_tooltip(self):
        """Cache l'info-bulle"""
        self.canvas.delete('tooltip')
    
    def start_resize(self, event, direction):
        self.resizing = True
        self.resize_direction = direction
        self.resize_start_mouse_x = event.x
        self.resize_start_mouse_y = event.y
        self.resize_orig_x = self.x
        self.resize_orig_y = self.y
        self.resize_orig_w = getattr(self, 'w', 100)
        self.resize_orig_h = getattr(self, 'h', 100)
        self.resize_orig_r = getattr(self, 'r', 75)
    
    def do_resize(self, event):
        if not self.resizing:
            return
        
        dx = event.x - self.resize_start_mouse_x
        dy = event.y - self.resize_start_mouse_y
        direction = self.resize_direction
        
        if self.type == 'logo':
            if direction in ['n', 's']:
                delta = dy if direction == 's' else -dy
            else:
                delta = dx if direction == 'e' else -dx
            
            new_r = max(20, self.resize_orig_r + delta)
            self.r = new_r
            self.canvas.coords(self.main_item,
                              self.x - self.r, self.y - self.r,
                              self.x + self.r, self.y + self.r)
            self.move_handles_only()
            
        elif self.type == 'texte':
            # Redimensionnement spécial pour le texte
            min_w, min_h = 100, 50
            new_x, new_y = self.resize_orig_x, self.resize_orig_y
            new_w, new_h = self.resize_orig_w, self.resize_orig_h
            
            if direction == 'se':
                new_w = max(min_w, self.resize_orig_w + dx)
                new_h = max(min_h, self.resize_orig_h + dy)
            elif direction == 'sw':
                new_w = max(min_w, self.resize_orig_w - dx)
                new_h = max(min_h, self.resize_orig_h + dy)
                new_x = self.resize_orig_x + (self.resize_orig_w - new_w)
            elif direction == 'ne':
                new_w = max(min_w, self.resize_orig_w + dx)
                new_h = max(min_h, self.resize_orig_h - dy)
                new_y = self.resize_orig_y + (self.resize_orig_h - new_h)
            elif direction == 'nw':
                new_w = max(min_w, self.resize_orig_w - dx)
                new_h = max(min_h, self.resize_orig_h - dy)
                new_x = self.resize_orig_x + (self.resize_orig_w - new_w)
                new_y = self.resize_orig_y + (self.resize_orig_h - new_h)
            
            self.x, self.y = new_x, new_y
            self.w, self.h = new_w, new_h
            self.custom_width = new_w
            self.custom_height = new_h
            
            # Mettre à jour le rectangle de fond et la bordure
            if len(self.items) >= 3:
                self.canvas.coords(self.items[0], self.x, self.y, self.x + self.w, self.y + self.h)
                self.canvas.coords(self.items[2], self.x, self.y, self.x + self.w, self.y + self.h)
                
                # Mettre à jour la largeur du texte
                if len(self.items) >= 2:
                    self.canvas.itemconfig(self.items[1], width=self.w - 20)
            
            self.move_handles_only()
            
        else:
            # Pour les autres types (banniere, gif, screenshot, badge)
            min_w, min_h = 50, 30
            new_x, new_y = self.resize_orig_x, self.resize_orig_y
            new_w, new_h = self.resize_orig_w, self.resize_orig_h
            
            if direction == 'se':
                new_w = max(min_w, self.resize_orig_w + dx)
                new_h = max(min_h, self.resize_orig_h + dy)
            elif direction == 'sw':
                new_w = max(min_w, self.resize_orig_w - dx)
                new_h = max(min_h, self.resize_orig_h + dy)
                new_x = self.resize_orig_x + (self.resize_orig_w - new_w)
            elif direction == 'ne':
                new_w = max(min_w, self.resize_orig_w + dx)
                new_h = max(min_h, self.resize_orig_h - dy)
                new_y = self.resize_orig_y + (self.resize_orig_h - new_h)
            elif direction == 'nw':
                new_w = max(min_w, self.resize_orig_w - dx)
                new_h = max(min_h, self.resize_orig_h - dy)
                new_x = self.resize_orig_x + (self.resize_orig_w - new_w)
                new_y = self.resize_orig_y + (self.resize_orig_h - new_h)
            
            self.x, self.y = new_x, new_y
            self.w, self.h = new_w, new_h
            self.canvas.coords(self.main_item, self.x, self.y, self.x + self.w, self.y + self.h)
            self.update_internal()
            self.move_handles_only()
    
    def move_handles_only(self):
        if not self.handles:
            return
        
        if self.type == 'logo':
            r = self.r
            positions = [
                (self.x, self.y - r), (self.x + r, self.y),
                (self.x, self.y + r), (self.x - r, self.y)
            ]
        else:
            w, h = self.w, self.h
            positions = [
                (self.x, self.y), (self.x + w, self.y),
                (self.x, self.y + h), (self.x + w, self.y + h)
            ]
        
        for i, (hx, hy) in enumerate(positions):
            if i < len(self.handles):
                self.canvas.coords(self.handles[i], hx-6, hy-6, hx+6, hy+6)
    
    def update_internal(self):
        if self.type == 'banniere':
            self.canvas.coords(self.text_item, self.x + self.w//2, self.y + self.h//2)
        elif self.type == 'gif':
            if len(self.items) >= 6:
                w, h = self.w, self.h
                self.canvas.coords(self.items[1], self.x, self.y, self.x + w, self.y + 25)
                self.canvas.coords(self.items[2], self.x + 10, self.y + 8, self.x + 18, self.y + 16)
                self.canvas.coords(self.items[3], self.x + 22, self.y + 8, self.x + 30, self.y + 16)
                self.canvas.coords(self.items[4], self.x + 34, self.y + 8, self.x + 42, self.y + 16)
                self.canvas.coords(self.text_item, self.x + w//2, self.y + h//2)
        elif self.type == 'screenshot':
            self.canvas.coords(self.text_item, self.x + self.w//2, self.y + self.h//2)
        elif self.type == 'badge':
            self.canvas.coords(self.text_item, self.x + self.w//2, self.y + self.h//2)
    
    def stop_resize(self, event):
        self.resizing = False
        self.resize_direction = None
        self.creer_poignees()
    
    def editer(self):
        """Édite l'élément avec option d'image locale"""
        if self.type == 'texte':
            self.editer_texte_avance()
            return
        
        # Récupérer l'application principale depuis la racine
        root = self.canvas.winfo_toplevel()
        app = None
        
        # Chercher l'attribut app dans la hiérarchie
        if hasattr(root, 'app'):
            app = root.app
        elif hasattr(self.canvas, 'app'):
            app = self.canvas.app
        else:
            # Dernier recours : chercher dans tous les enfants
            for widget in root.winfo_children():
                if hasattr(widget, 'app'):
                    app = widget.app
                    break
        
        dialog = tk.Toplevel(root)
        dialog.title(f"Éditer {self.type}")
        dialog.configure(bg='#161b22')
        dialog.geometry("500x450")
        dialog.transient(root)
        dialog.grab_set()
    
        # En-tête
        tk.Label(dialog, text=f"Type: {self.type.upper()}", 
                font=('Segoe UI', 14, 'bold'), bg='#161b22', fg='#f0f6fc').pack(pady=10)
        
        entries = {}
        
        # Champ texte si disponible
        if hasattr(self, 'text_item') and self.type != 'screenshot':
            tk.Label(dialog, text="Texte:", bg='#161b22', fg='#c9d1d9').pack(anchor='w', padx=20)
            entry = tk.Entry(dialog, font=('Consolas', 11), bg='#0d1117', fg='#f0f6fc')
            entry.pack(fill='x', padx=20, pady=5)
            entry.insert(0, self.canvas.itemcget(self.text_item, 'text'))
            entries['texte'] = entry
        
        # Section URL pour les éléments d'image
        if self.type in ['banniere', 'logo', 'gif', 'screenshot']:
            # Frame pour l'URL
            url_frame = tk.Frame(dialog, bg='#161b22')
            url_frame.pack(fill='x', padx=20, pady=10)
            
            tk.Label(url_frame, text="URL de l'image:", 
                    bg='#161b22', fg='#c9d1d9', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
            
            # Champ URL
            url_entry = tk.Entry(url_frame, font=('Consolas', 10), bg='#0d1117', fg='#f0f6fc')
            url_entry.pack(fill='x', pady=5)
            url_entry.insert(0, self.kwargs.get('url', ''))
            entries['url'] = url_entry
            
            # Frame pour les boutons d'image
            img_buttons = tk.Frame(url_frame, bg='#161b22')
            img_buttons.pack(fill='x', pady=5)
            
            def choisir_image():
                """Choisir une image locale"""
                app = self.canvas.winfo_toplevel().app  # Récupérer l'application principale
                chemin = app.choisir_image_locale()
                if chemin:
                    url_entry.delete(0, 'end')
                    url_entry.insert(0, chemin)
            
            def parcourir_images():
                """Ouvrir le dossier images"""
                app = self.canvas.winfo_toplevel().app
                app.ouvrir_dossier_images()
            
            # Bouton pour choisir une image locale
            tk.Button(img_buttons, text="📁 Choisir image locale", command=choisir_image,
                     bg='#1f6feb', fg='white', font=('Segoe UI', 9, 'bold'),
                     relief='flat', padx=10).pack(side='left', padx=5)
            
            # Bouton pour ouvrir le dossier images
            tk.Button(img_buttons, text="📂 Ouvrir dossier images", command=parcourir_images,
                     bg='#238636', fg='white', font=('Segoe UI', 9, 'bold'),
                     relief='flat', padx=10).pack(side='left', padx=5)
            
            # Info sur le chemin relatif
            tk.Label(url_frame, text="💡 Les images locales seront copiées dans le dossier 'images/'", 
                    bg='#161b22', fg='#8b949e', font=('Segoe UI', 8)).pack(anchor='w', pady=5)
        
        # Options spécifiques au badge
        if self.type == 'badge':
            tk.Label(dialog, text="Couleur:", bg='#161b22', fg='#c9d1d9').pack(anchor='w', padx=20, pady=(10,0))
            var = tk.StringVar(value=self.kwargs.get('couleur', 'blue'))
            
            color_frame = tk.Frame(dialog, bg='#161b22')
            color_frame.pack(fill='x', padx=20, pady=5)
            
            couleurs = [
                ('blue', '#007ec6'), ('green', '#4c1'), 
                ('yellow', '#dfb317'), ('red', '#e05d44')
            ]
            
            for c_name, c_code in couleurs:
                rb = tk.Radiobutton(color_frame, text=c_name, variable=var, value=c_name,
                                   bg='#161b22', fg='#c9d1d9', selectcolor='#238636')
                rb.pack(side='left', padx=10)
            
            entries['couleur'] = var
        
        # Options spécifiques au screenshot
        if self.type == 'screenshot':
            tk.Label(dialog, text="Description:", bg='#161b22', fg='#c9d1d9').pack(anchor='w', padx=20, pady=(10,0))
            desc_entry = tk.Entry(dialog, font=('Consolas', 11), bg='#0d1117', fg='#f0f6fc')
            desc_entry.pack(fill='x', padx=20, pady=5)
            desc_entry.insert(0, self.kwargs.get('description', 'Screenshot'))
            entries['description'] = desc_entry
        
        def save():
            """Sauvegarde les modifications"""
            # Sauvegarder le texte
            if 'texte' in entries and hasattr(self, 'text_item'):
                self.kwargs['texte'] = entries['texte'].get()
                self.canvas.itemconfig(self.text_item, text=self.kwargs['texte'])
            
            # Sauvegarder l'URL
            if 'url' in entries:
                self.kwargs['url'] = entries['url'].get()
            
            # Sauvegarder la description
            if 'description' in entries:
                self.kwargs['description'] = entries['description'].get()
            
            # Sauvegarder la couleur du badge
            if 'couleur' in entries and self.type == 'badge':
                self.kwargs['couleur'] = entries['couleur'].get()
                couleurs = {'blue': '#007ec6', 'green': '#4c1', 'yellow': '#dfb317', 'red': '#e05d44'}
                self.canvas.itemconfig(self.main_item, fill=couleurs.get(self.kwargs['couleur'], '#007ec6'))
            
            # Mettre à jour l'affichage du texte si nécessaire
            if self.type == 'screenshot' and hasattr(self, 'text_item'):
                desc = self.kwargs.get('description', 'Screenshot')
                self.canvas.itemconfig(self.text_item, text=f"📸 {desc}")
            
            dialog.destroy()
            self.canvas.sauver_etat()  # Sauvegarder l'état pour undo
        
        # Boutons de sauvegarde
        btn_frame = tk.Frame(dialog, bg='#161b22')
        btn_frame.pack(fill='x', padx=20, pady=20)
        
        tk.Button(btn_frame, text="💾 Sauvegarder", command=save,
                 bg='#238636', fg='white', font=('Segoe UI', 12, 'bold'),
                 relief='flat', padx=20).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="❌ Annuler", command=dialog.destroy,
                 bg='#da3633', fg='white', font=('Segoe UI', 12, 'bold'),
                 relief='flat', padx=20).pack(side='left', padx=5)

    def editer_texte_avance(self):
        """Éditeur de texte avancé avec options de formatage"""
        if self.type != 'texte':
            return self.editer()
        
        dialog = tk.Toplevel(self.canvas.winfo_toplevel())
        dialog.title("Éditeur de texte avancé")
        dialog.configure(bg='#161b22')
        dialog.geometry("600x500")
        dialog.transient(self.canvas.winfo_toplevel())
        dialog.grab_set()
        
        # Frame pour les options de formatage
        toolbar = tk.Frame(dialog, bg='#21262d', height=40)
        toolbar.pack(fill='x', padx=10, pady=10)
        
        # Variables pour le formatage
        current_font = self.kwargs.get('font', ('Segoe UI', 12))
        current_size = current_font[1] if isinstance(current_font, tuple) else 12
        current_family = current_font[0] if isinstance(current_font, tuple) else 'Segoe UI'
        
        # Police
        tk.Label(toolbar, text="Police:", bg='#21262d', fg='#f0f6fc').pack(side='left', padx=5)
        font_var = tk.StringVar(value=current_family)
        fonts = ['Segoe UI', 'Arial', 'Courier New', 'Georgia', 'Times New Roman', 'Verdana']
        font_menu = ttk.Combobox(toolbar, textvariable=font_var, values=fonts, width=12)
        font_menu.pack(side='left', padx=5)
        
        # Taille
        tk.Label(toolbar, text="Taille:", bg='#21262d', fg='#f0f6fc').pack(side='left', padx=5)
        size_var = tk.IntVar(value=current_size)
        size_spin = tk.Spinbox(toolbar, from_=8, to=72, textvariable=size_var, width=5)
        size_spin.pack(side='left', padx=5)
        
        # Couleur
        tk.Label(toolbar, text="Couleur:", bg='#21262d', fg='#f0f6fc').pack(side='left', padx=5)
        color_var = tk.StringVar(value=self.kwargs.get('couleur', '#f0f6fc'))
        colors = ['#f0f6fc', '#ff7b72', '#79c0ff', '#7ee787', '#d2a8ff', '#ffa657']
        color_menu = ttk.Combobox(toolbar, textvariable=color_var, values=colors, width=10)
        color_menu.pack(side='left', padx=5)
        
        # Boutons de formatage
        tk.Button(toolbar, text="B", font=('Segoe UI', 10, 'bold'),
                 bg='#21262d', fg='#f0f6fc', command=lambda: inserer_balise('**')).pack(side='left', padx=2)
        tk.Button(toolbar, text="I", font=('Segoe UI', 10, 'italic'),
                 bg='#21262d', fg='#f0f6fc', command=lambda: inserer_balise('*')).pack(side='left', padx=2)
        tk.Button(toolbar, text="• Liste", bg='#21262d', fg='#f0f6fc',
                 command=lambda: inserer_balise('- ')).pack(side='left', padx=2)
        tk.Button(toolbar, text="1. Liste", bg='#21262d', fg='#f0f6fc',
                 command=lambda: inserer_balise('1. ')).pack(side='left', padx=2)
        tk.Button(toolbar, text="[Lien]", bg='#21262d', fg='#f0f6fc',
                 command=lambda: inserer_balise('[texte](url)')).pack(side='left', padx=2)
        
        # Zone de texte
        text_frame = tk.Frame(dialog, bg='#0d1117')
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, font=(current_family, current_size),
                             bg='#0d1117', fg=color_var.get(),
                             wrap='word', height=15)
        text_widget.pack(fill='both', expand=True, side='left')
        
        scrollbar = tk.Scrollbar(text_frame, command=text_widget.yview)
        scrollbar.pack(side='right', fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # Charger le texte existant
        current_text = self.canvas.itemcget(self.text_item, 'text')
        text_widget.insert('1.0', current_text)
        
        def inserer_balise(balise):
            """Insère une balise de formatage"""
            try:
                text_widget.insert(tk.INSERT, balise)
            except:
                pass
        
        def appliquer_style():
            """Applique les changements de style"""
            try:
                new_font = (font_var.get(), size_var.get())
                new_color = color_var.get()
                
                # Mettre à jour l'affichage
                text_widget.config(font=new_font, fg=new_color)
            except:
                pass
        
        # Lier les changements de style
        font_menu.bind('<<ComboboxSelected>>', lambda e: appliquer_style())
        size_spin.bind('<KeyRelease>', lambda e: appliquer_style())
        color_menu.bind('<<ComboboxSelected>>', lambda e: appliquer_style())
        
        def save():
            """Sauvegarde le texte formaté"""
            new_text = text_widget.get('1.0', 'end-1c')
            new_font = (font_var.get(), size_var.get())
            new_color = color_var.get()
            
            self.kwargs['texte'] = new_text
            self.kwargs['font'] = new_font
            self.kwargs['couleur'] = new_color
            
            # Supprimer l'ancien texte
            for item in self.items:
                self.canvas.delete(item)
            self.items = []
            
            # Recréer avec les nouveaux paramètres
            self.creer_texte()
            
            # Mettre à jour les poignées si sélectionné
            if self.selected:
                self.deselectionner()
                self.selectionner()
            
            dialog.destroy()
        
        # Boutons de sauvegarde
        btn_frame = tk.Frame(dialog, bg='#161b22')
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(btn_frame, text="💾 Sauvegarder", command=save,
                 bg='#238636', fg='white', font=('Segoe UI', 11, 'bold'),
                 relief='flat').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="❌ Annuler", command=dialog.destroy,
                 bg='#da3633', fg='white', font=('Segoe UI', 11, 'bold'),
                 relief='flat').pack(side='left', padx=5)
    
    def supprimer(self):
        self.deselectionner()
        for item in self.items:
            self.canvas.delete(item)
    
    def to_dict(self):
        return {
            'type': self.type, 'x': self.x, 'y': self.y,
            'w': getattr(self, 'w', None), 'h': getattr(self, 'h', None),
            'r': getattr(self, 'r', None), 'kwargs': self.kwargs
        }
    
    def from_dict(self, data):
        """Restaure depuis un dictionnaire"""
        self.x = data['x']
        self.y = data['y']
        if data.get('w'): 
            self.w = data['w']
            if self.type == 'texte':
                self.custom_width = data['w']
        if data.get('h'): 
            self.h = data['h']
            if self.type == 'texte':
                self.custom_height = data['h']
        if data.get('r'): self.r = data['r']
        self.kwargs = data.get('kwargs', {})
        
        # Supprimer anciens items
        for item in self.items:
            self.canvas.delete(item)
        self.items = []
        
        # Recréer
        self.creer()
        
        # Déplacer à la bonne position
        dx = self.x - data['x']
        dy = self.y - data['y']
        for item in self.items:
            self.canvas.move(item, dx, dy)

class EditeurVisuel(tk.Canvas):
    """Canvas principal avec gestion des éléments et historique"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg='#0d1117', highlightthickness=2, 
                        highlightbackground='#30363d', width=1200, height=900, **kwargs)
        
        self.elements = []
        self.element_selectionne = None
        self.historique = Historique(max_size=50)
        self.magnetisme = False  # Grille magnétique
        self.zoom_factor = 1.0  # ← Remplacer 'scale' par 'zoom_factor'
        self.grille_visible = True  # Grille visible par défaut
        
        self.dessiner_grille()
        self.sauver_etat()  # État initial pour undo
        
        self.bind('<Button-1>', self.on_canvas_click)
        self.bind('<Delete>', self.on_delete)
        self.bind('<KeyPress>', self.on_key)
        self.bind('<Control-z>', self.undo)
        self.bind('<Control-y>', self.redo)
        self.bind('<Control-d>', self.dupliquer)
        self.bind('<Configure>', self.on_resize)
        self.focus_set()
        self.bind('<Button-1>', lambda e: self.focus_set())

        # Référence à l'application principale
        self.app = None
    
    def on_resize(self, event):
        """Redessine la grille quand le canvas est redimensionné"""
        self.dessiner_grille()
    
    def dessiner_grille(self):
        """Dessine la grille adaptée à la taille du canvas"""
        if not getattr(self, 'grille_visible', True):
            return
        
        self.delete('grille')
        
        # Obtenir les dimensions actuelles du canvas
        width = self.winfo_width()
        height = self.winfo_height()
        
        # Si les dimensions ne sont pas encore disponibles, utiliser les valeurs par défaut
        if width <= 1:
            width = 1200
        if height <= 1:
            height = 900
        
        # Dessiner les lignes verticales tous les 50px
        for i in range(0, width + 50, 50):
            self.create_line(i, 0, i, height, fill='#21262d', tags='grille')
        
        # Dessiner les lignes horizontales tous les 50px
        for i in range(0, height + 50, 50):
            self.create_line(0, i, width, i, fill='#21262d', tags='grille')
        
        self.tag_lower('grille')
    
    def on_canvas_click(self, event):
        items = self.find_closest(event.x, event.y)
        if items:
            tags = self.gettags(items[0])
            if 'element' in tags or 'handle' in tags:
                return
        self.deselectionner_tout()
    
    def on_delete(self, event):
        if self.element_selectionne:
            self.sauver_etat()  # Pour undo
            self.element_selectionne.supprimer()
            self.elements.remove(self.element_selectionne)
            self.element_selectionne = None
    
    def on_key(self, event):
        if event.keysym == 'Delete':
            self.on_delete(event)
        elif self.element_selectionne and event.keysym in ['Up', 'Down', 'Left', 'Right']:
            # Déplacement précis avec flèches
            dx, dy = 0, 0
            step = 10 if not self.magnetisme else 50
            if event.keysym == 'Up': dy = -step
            elif event.keysym == 'Down': dy = step
            elif event.keysym == 'Left': dx = -step
            elif event.keysym == 'Right': dx = step
            
            self.sauver_etat()
            elem = self.element_selectionne
            for item in elem.items:
                self.move(item, dx, dy)
            for handle in elem.handles:
                self.move(handle, dx, dy)
            elem.x += dx
            elem.y += dy
    
    def undo(self, event=None):
        """Annuler"""
        etat = self.historique.undo()
        if etat:
            self.restaurer_etat(etat)
            return 'break'
    
    def redo(self, event=None):
        """Refaire"""
        etat = self.historique.redo()
        if etat:
            self.restaurer_etat(etat)
            return 'break'
    
    def dupliquer(self, event=None):
        """Dupliquer l'élément sélectionné"""
        if not self.element_selectionne:
            return 'break'
        
        self.sauver_etat()
        original = self.element_selectionne
        
        # Créer une copie
        new_elem = ElementCanvas(self, original.type, 
                                original.x + 30, original.y + 30,
                                **original.kwargs)
        
        # Copier les dimensions
        if hasattr(original, 'w'): new_elem.w = original.w
        if hasattr(original, 'h'): new_elem.h = original.h
        if hasattr(original, 'r'): new_elem.r = original.r
        
        self.elements.append(new_elem)
        self.deselectionner_tout()
        self.selectionner_element(new_elem)
        new_elem.selectionner()
        
        return 'break'
    
    def sauver_etat(self):
        """Sauvegarde l'état actuel pour undo"""
        etat = [elem.to_dict() for elem in self.elements]
        self.historique.push(etat)
    
    def restaurer_etat(self, etat):
        """Restaure un état depuis l'historique"""
        # Supprimer tous les éléments actuels
        for elem in self.elements:
            elem.supprimer()
        self.elements = []
        self.element_selectionne = None
        
        # Recréer depuis l'état
        for elem_data in etat:
            elem = ElementCanvas(self, elem_data['type'], 
                               elem_data['x'], elem_data['y'],
                               **elem_data.get('kwargs', {}))
            if elem_data.get('w'): elem.w = elem_data['w']
            if elem_data.get('h'): elem.h = elem_data['h']
            if elem_data.get('r'): elem.r = elem_data['r']
            self.elements.append(elem)
    
    def ajouter_element(self, type_elem, **kwargs):
        self.sauver_etat()
        x = 100 + (len(self.elements) * 30) % 400
        y = 50 + (len(self.elements) * 20) % 300
        
        element = ElementCanvas(self, type_elem, x, y, **kwargs)
        self.elements.append(element)
        return element
    
    def selectionner_element(self, element):
        self.deselectionner_tout()
        self.element_selectionne = element
    
    def deselectionner_tout(self):
        if self.element_selectionne:
            self.element_selectionne.deselectionner()
            self.element_selectionne = None
    
    def toggle_magnetisme(self):
        """Active/désactive la grille magnétique"""
        self.magnetisme = not self.magnetisme
        return self.magnetisme
    
    def aligner_elements(self, direction):
        """Aligne tous les éléments"""
        if not self.elements:
            return
        
        self.sauver_etat()
        
        if direction == 'gauche':
            min_x = min(e.x for e in self.elements)
            for elem in self.elements:
                dx = min_x - elem.x
                for item in elem.items:
                    self.move(item, dx, 0)
                for handle in elem.handles:
                    self.move(handle, dx, 0)
                elem.x = min_x
        
        elif direction == 'droite':
            max_x_right = max(e.x + getattr(e, 'w', 100) for e in self.elements)
            for elem in self.elements:
                w = getattr(elem, 'w', 100)
                new_x = max_x_right - w
                dx = new_x - elem.x
                for item in elem.items:
                    self.move(item, dx, 0)
                for handle in elem.handles:
                    self.move(handle, dx, 0)
                elem.x = new_x
        
        elif direction == 'haut':
            min_y = min(e.y for e in self.elements)
            for elem in self.elements:
                dy = min_y - elem.y
                for item in elem.items:
                    self.move(item, 0, dy)
                for handle in elem.handles:
                    self.move(handle, 0, dy)
                elem.y = min_y
        
        elif direction == 'centre':
            # Centrer horizontalement
            center_x = 440  # 880 / 2
            for elem in self.elements:
                w = getattr(elem, 'w', 100)
                new_x = center_x - w // 2
                dx = new_x - elem.x
                for item in elem.items:
                    self.move(item, dx, 0)
                for handle in elem.handles:
                    self.move(handle, dx, 0)
                elem.x = new_x
    
    def exporter_markdown(self, tableau=False):
        """Exporte en Markdown en respectant la position et la taille des éléments"""
        
        # Trier les éléments par position Y (haut en bas) puis X (gauche à droite)
        elements_sorted = sorted(self.elements, key=lambda e: (e.y, e.x))
        
        markdown = "<div align='center'>\n\n"
        
        # Grouper les éléments par proximité verticale (lignes)
        lignes = []
        ligne_actuelle = []
        seuil_ligne = 50  # Distance en pixels pour considérer que des éléments sont sur la même ligne
        
        for elem in elements_sorted:
            if not ligne_actuelle:
                ligne_actuelle = [elem]
            else:
                # Si l'élément est proche verticalement du dernier élément de la ligne
                if abs(elem.y - ligne_actuelle[0].y) < seuil_ligne:
                    ligne_actuelle.append(elem)
                else:
                    # Nouvelle ligne
                    lignes.append(ligne_actuelle)
                    ligne_actuelle = [elem]
        
        if ligne_actuelle:
            lignes.append(ligne_actuelle)
        
        # Exporter chaque ligne
        for ligne in lignes:
            # Trier les éléments de la ligne par X (gauche à droite)
            ligne.sort(key=lambda e: e.x)
            
            # Si plusieurs éléments sur la même ligne, utiliser flexbox
            if len(ligne) > 1:
                markdown += "<div style='display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;'>\n\n"
                
                for elem in ligne:
                    markdown += self._element_to_markdown(elem)
                
                markdown += "\n</div>\n\n"
            else:
                # Un seul élément sur la ligne
                markdown += self._element_to_markdown(ligne[0])
        
        markdown += "</div>"
        return markdown

    def _element_to_markdown(self, elem):
        """Convertit un élément en markdown avec ses dimensions"""
        md = ""
        
        # Fonction pour nettoyer l'URL
        def get_image_url(url):
            if url and not url.startswith(('http://', 'https://')):
                # C'est un chemin local, s'assurer qu'il commence par ./
                if not url.startswith(('./', 'images/')):
                    return f"./{url}"
            return url
        
        if elem.type == 'banniere':
            if elem.kwargs.get('url'):
                width = getattr(elem, 'w', 700)
                url = get_image_url(elem.kwargs['url'])
                md += f"<img src='{url}' width='{width}px' alt='Bannière'><br>\n"
            md += f"# {elem.kwargs.get('texte', 'Titre')}\n\n"
        
        elif elem.type == 'logo':
            if elem.kwargs.get('url'):
                size = getattr(elem, 'r', 75) * 2
                url = get_image_url(elem.kwargs['url'])
                md += f"<img src='{url}' width='{size}px' style='border-radius:50%'><br>\n"
            else:
                md += f"<h2>{elem.kwargs.get('texte', 'LO')[:2].upper()}</h2>\n"
        
        elif elem.type == 'gif':
            if elem.kwargs.get('url'):
                width = getattr(elem, 'w', 400)
                url = get_image_url(elem.kwargs['url'])
                md += f"<img src='{url}' width='{width}px' alt='Demo'><br>\n\n"
        
        elif elem.type == 'screenshot':
            if elem.kwargs.get('url'):
                width = getattr(elem, 'w', 330)
                url = get_image_url(elem.kwargs['url'])
                desc = elem.kwargs.get('description', 'Screenshot')
                md += f"<img src='{url}' width='{width}px' alt='{desc}'>\n\n"
        
        elif elem.type == 'badge':
            couleurs = {'blue': 'blue', 'green': 'brightgreen', 'yellow': 'yellow', 'red': 'red'}
            color = couleurs.get(elem.kwargs.get('couleur', 'blue'), 'blue')
            texte = elem.kwargs.get('texte', 'badge')
            md += f"<img src='https://img.shields.io/badge/{texte.replace(' ', '%20')}-{color}'> "
        
        elif elem.type == 'texte':
            # Récupérer le texte formaté
            texte = elem.kwargs.get('texte', '')
            font_family = elem.kwargs.get('font_family', 'Segoe UI')
            font_size = elem.kwargs.get('font_size', 12)
            couleur = elem.kwargs.get('couleur', '#f0f6fc')
            
            # Convertir le texte simple en markdown avec style
            if texte:
                # Remplacer les balises simples par du markdown
                texte = texte.replace('**', '**').replace('*', '*')
                md += f"{texte}\n\n"
        
        return md

    def update_scrollregion(self):
        """Met à jour la zone de défilement"""
        bbox = self.bbox("all")
        if bbox:
            self.config(scrollregion=bbox)
        else:
            self.config(scrollregion=(0, 0, 1200, 900))

class OutilCapture:
    """Gère les captures d'écran et d'écran"""
    
    def __init__(self, app):
        self.app = app
        self.capture_active = False
        self.selection = None
        self.root = app.root
        
        # Créer la fenêtre de sélection (cachée au départ)
        self.creer_fenetre_selection()
    
    def creer_fenetre_selection(self):
        """Crée une fenêtre transparente pour la sélection"""
        self.selection_window = tk.Toplevel(self.root)
        self.selection_window.withdraw()  # Cachée au départ
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.attributes('-topmost', True)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.configure(bg='black')
        
        # Canvas pour dessiner la sélection
        self.selection_canvas = tk.Canvas(self.selection_window, 
                                         highlightthickness=0, bg='black')
        self.selection_canvas.pack(fill='both', expand=True)
        
        # Variables pour la sélection
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        
        # Bindings
        self.selection_canvas.bind('<Button-1>', self.on_selection_start)
        self.selection_canvas.bind('<B1-Motion>', self.on_selection_drag)
        self.selection_canvas.bind('<ButtonRelease-1>', self.on_selection_end)
        self.selection_window.bind('<Escape>', self.annuler_selection)
    
    def capturer_zone(self, type_capture='screenshot'):
        """Démarre la capture d'une zone"""
        self.type_capture = type_capture
        self.capture_active = True
        
        # Cacher la fenêtre principale temporairement
        self.root.withdraw()
        
        # Attendre un peu pour que la fenêtre se cache
        self.root.after(500, self.afficher_selection)
    
    def afficher_selection(self):
        """Affiche la fenêtre de sélection"""
        self.selection_window.deiconify()
        self.selection_canvas.delete('all')
        self.start_x = None
        self.start_y = None
        
        # Instructions
        self.selection_canvas.create_text(
            self.selection_window.winfo_screenwidth() // 2, 30,
            text="Cliquez et glissez pour sélectionner une zone | ESC pour annuler",
            fill='white', font=('Segoe UI', 14, 'bold')
        )
    
    def on_selection_start(self, event):
        """Début de la sélection"""
        self.start_x = event.x
        self.start_y = event.y
        
        if self.current_rect:
            self.selection_canvas.delete(self.current_rect)
    
    def on_selection_drag(self, event):
        """Pendant la sélection"""
        if self.start_x is None or self.start_y is None:
            return
        
        if self.current_rect:
            self.selection_canvas.delete(self.current_rect)
        
        # Dessiner le rectangle de sélection
        self.current_rect = self.selection_canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline='#f78166', fill='#f78166', stipple='gray25', width=3
        )
        
        # Afficher les dimensions
        width = abs(event.x - self.start_x)
        height = abs(event.y - self.start_y)
        
        # Supprimer l'ancien texte
        self.selection_canvas.delete('dimensions')
        
        # Afficher les nouvelles dimensions
        self.selection_canvas.create_text(
            (self.start_x + event.x) // 2,
            (self.start_y + event.y) // 2 - 20,
            text=f"{width} x {height} px",
            fill='white', font=('Segoe UI', 12, 'bold'),
            tags='dimensions'
        )
    
    def on_selection_end(self, event):
        """Fin de la sélection"""
        if self.start_x is None:
            return
        
        # Calculer les coordonnées de la sélection
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        
        self.selection = (x1, y1, x2, y2)
        
        # Cacher la fenêtre de sélection
        self.selection_window.withdraw()
        
        # Effectuer la capture
        self.effectuer_capture()
    
    def annuler_selection(self, event=None):
        """Annule la sélection"""
        self.selection_window.withdraw()
        self.root.deiconify()
        self.capture_active = False
    
    def effectuer_capture(self):
        """Effectue la capture selon le type demandé"""
        if not self.selection:
            self.root.deiconify()
            return
        
        x1, y1, x2, y2 = self.selection
        
        # Attendre un peu pour que la fenêtre de sélection se cache
        time.sleep(0.3)
        
        if self.type_capture == 'screenshot':
            self.capturer_image(x1, y1, x2, y2)
        elif self.type_capture == 'gif':
            self.capturer_gif(x1, y1, x2, y2)
        elif self.type_capture == 'video':
            self.capturer_video(x1, y1, x2, y2)
        
        # Réafficher la fenêtre principale
        self.root.deiconify()
    
    def capturer_image(self, x1, y1, x2, y2):
        """Capture une image de la zone sélectionnée"""
        try:
            # Capturer l'écran
            screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            
            # Créer le dossier images s'il n'existe pas
            images_dir = Path.cwd() / "images"
            images_dir.mkdir(exist_ok=True)
            
            # Générer un nom de fichier
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = images_dir / f"screenshot_{timestamp}.png"
            
            # Sauvegarder
            screenshot.save(filename)
            
            # Proposer d'ajouter au canvas
            self.proposer_ajout_canvas(str(filename), 'screenshot')
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de capturer : {str(e)}")
    
    def capturer_gif(self, x1, y1, x2, y2):
        """Capture une séquence GIF de la zone sélectionnée"""
        try:
            # Demander la durée et le framerate
            dialog = tk.Toplevel(self.root)
            dialog.title("Capture GIF")
            dialog.geometry("400x250")
            dialog.configure(bg='#161b22')
            dialog.transient(self.root)
            dialog.grab_set()
            
            tk.Label(dialog, text="Capture GIF animé", 
                    font=('Segoe UI', 14, 'bold'),
                    bg='#161b22', fg='#f0f6fc').pack(pady=10)
            
            tk.Label(dialog, text="Durée (secondes):", 
                    bg='#161b22', fg='#c9d1d9').pack(pady=5)
            duree_var = tk.StringVar(value="3")
            duree_entry = tk.Entry(dialog, textvariable=duree_var, width=10)
            duree_entry.pack()
            
            tk.Label(dialog, text="Images par seconde:", 
                    bg='#161b22', fg='#c9d1d9').pack(pady=5)
            fps_var = tk.StringVar(value="10")
            fps_entry = tk.Entry(dialog, textvariable=fps_var, width=10)
            fps_entry.pack()
            
            def demarrer_capture():
                try:
                    duree = float(duree_var.get())
                    fps = int(fps_var.get())
                    dialog.destroy()
                    
                    # Lancer la capture dans un thread séparé
                    threading.Thread(
                        target=self.capturer_gif_thread,
                        args=(x1, y1, x2, y2, duree, fps),
                        daemon=True
                    ).start()
                    
                except ValueError:
                    messagebox.showerror("Erreur", "Valeurs invalides")
            
            tk.Button(dialog, text="Démarrer", command=demarrer_capture,
                     bg='#238636', fg='white', font=('Segoe UI', 11, 'bold'),
                     relief='flat', padx=20).pack(pady=15)
            
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
    
    def capturer_gif_thread(self, x1, y1, x2, y2, duree, fps):
        """Thread de capture GIF"""
        try:
            images = []
            n_frames = int(duree * fps)
            interval = 1.0 / fps
            
            # Afficher un compteur
            self.root.after(0, lambda: self.afficher_progression(f"Capture GIF: 0/{n_frames}"))
            
            for i in range(n_frames):
                # Capturer l'écran
                img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                images.append(img)
                
                # Mettre à jour la progression
                if i % fps == 0:
                    self.root.after(0, lambda i=i: self.afficher_progression(f"Capture GIF: {i+1}/{n_frames}"))
                
                time.sleep(interval)
            
            # Créer le dossier images
            images_dir = Path.cwd() / "images"
            images_dir.mkdir(exist_ok=True)
            
            # Sauvegarder le GIF
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = images_dir / f"animation_{timestamp}.gif"
            
            images[0].save(
                filename,
                save_all=True,
                append_images=images[1:],
                duration=int(interval * 1000),
                loop=0
            )
            
            self.root.after(0, lambda: self.afficher_progression(""))
            self.root.after(0, lambda: self.proposer_ajout_canvas(str(filename), 'gif'))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erreur", str(e)))
    
    def capturer_video(self, x1, y1, x2, y2):
        """Capture une vidéo de la zone sélectionnée"""
        try:
            # Demander les paramètres
            dialog = tk.Toplevel(self.root)
            dialog.title("Capture Vidéo")
            dialog.geometry("400x300")
            dialog.configure(bg='#161b22')
            dialog.transient(self.root)
            dialog.grab_set()
            
            tk.Label(dialog, text="Capture Vidéo", 
                    font=('Segoe UI', 14, 'bold'),
                    bg='#161b22', fg='#f0f6fc').pack(pady=10)
            
            tk.Label(dialog, text="Durée (secondes):", 
                    bg='#161b22', fg='#c9d1d9').pack(pady=5)
            duree_var = tk.StringVar(value="5")
            tk.Entry(dialog, textvariable=duree_var, width=10).pack()
            
            tk.Label(dialog, text="Images par seconde:", 
                    bg='#161b22', fg='#c9d1d9').pack(pady=5)
            fps_var = tk.StringVar(value="15")
            tk.Entry(dialog, textvariable=fps_var, width=10).pack()
            
            def demarrer_capture():
                try:
                    duree = float(duree_var.get())
                    fps = int(fps_var.get())
                    dialog.destroy()
                    
                    # Lancer la capture vidéo
                    threading.Thread(
                        target=self.capturer_video_thread,
                        args=(x1, y1, x2, y2, duree, fps),
                        daemon=True
                    ).start()
                    
                except ValueError:
                    messagebox.showerror("Erreur", "Valeurs invalides")
            
            tk.Button(dialog, text="Démarrer", command=demarrer_capture,
                     bg='#238636', fg='white', font=('Segoe UI', 11, 'bold'),
                     relief='flat', padx=20).pack(pady=15)
            
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
    
    def capturer_video_thread(self, x1, y1, x2, y2, duree, fps):
        """Thread de capture vidéo"""
        try:
            # Préparer le fichier de sortie
            images_dir = Path.cwd() / "images"
            images_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = images_dir / f"video_{timestamp}.mp4"
            
            # Dimensions
            width = x2 - x1
            height = y2 - y1
            
            # Préparer le writer vidéo
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(filename), fourcc, fps, (width, height))
            
            n_frames = int(duree * fps)
            
            for i in range(n_frames):
                # Capturer l'écran
                img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                
                # Convertir en format OpenCV
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                
                # Écrire la frame
                out.write(frame)
                
                # Mettre à jour la progression
                if i % fps == 0:
                    self.root.after(0, lambda i=i: self.afficher_progression(f"Capture vidéo: {i+1}/{n_frames}"))
                
                time.sleep(1.0 / fps)
            
            out.release()
            
            self.root.after(0, lambda: self.afficher_progression(""))
            messagebox.showinfo("Succès", f"Vidéo sauvegardée :\n{filename}")
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erreur", str(e)))
    
    def afficher_progression(self, message):
        """Affiche un message de progression"""
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text=message)
        else:
            self.progress_label = tk.Label(
                self.root, text=message, bg='#0d1117', fg='#f0f6fc'
            )
            self.progress_label.pack(side='bottom', pady=5)
    
    def proposer_ajout_canvas(self, chemin_image, type_elem):
        """Propose d'ajouter l'image capturée au canvas"""
        if messagebox.askyesno("Ajouter au canvas", 
                               f"Voulez-vous ajouter cette {type_elem} au canvas ?"):
            # Ajouter l'élément au canvas
            self.app.canvas_editor.ajouter_element(
                type_elem, 
                url=chemin_image,
                description=f"Capture du {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
class ApplicationPrincipale:
    def __init__(self, root):
        self.root = root
        self.root.title("🎨 Éditeur WYSIWYG README Pro")
        self.root.geometry("1800x1050")
        self.root.configure(bg='#0d1117')
        self.root.minsize(1400, 800)  # Taille minimum

        self.root.app = self    
    
        # la barre de menu
        self.creer_menu()
        
        # l'attribut pour copier
        self.copied_element = None
    
        self.creer_interface()

    def creer_menu(self):
        """Crée la barre de menu complète"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0, bg='#161b22', fg='#f0f6fc')
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Nouveau", command=self.nouveau_projet, accelerator="Ctrl+N")
        file_menu.add_command(label="Ouvrir...", command=self.ouvrir_projet, accelerator="Ctrl+O")
        file_menu.add_command(label="Sauvegarder", command=self.sauvegarder_projet, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exporter Markdown", command=self.generer_markdown, accelerator="Ctrl+E")
        file_menu.add_command(label="Exporter HTML", command=self.exporter_html)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.root.quit, accelerator="Ctrl+Q")
        
        # Menu Édition
        edit_menu = tk.Menu(menubar, tearoff=0, bg='#161b22', fg='#f0f6fc')
        menubar.add_cascade(label="Édition", menu=edit_menu)
        edit_menu.add_command(label="Annuler", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Rétablir", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Couper", command=self.couper, accelerator="Ctrl+X")
        edit_menu.add_command(label="Copier", command=self.copier_element, accelerator="Ctrl+C")
        edit_menu.add_command(label="Coller", command=self.coller, accelerator="Ctrl+V")
        edit_menu.add_command(label="Dupliquer", command=self.dupliquer, accelerator="Ctrl+D")
        edit_menu.add_separator()
        edit_menu.add_command(label="Supprimer", command=self.supprimer_selection, accelerator="Suppr")
        edit_menu.add_command(label="Tout sélectionner", command=self.tout_selectionner, accelerator="Ctrl+A")
        
        # Menu Outils
        tools_menu = tk.Menu(menubar, tearoff=0, bg='#161b22', fg='#f0f6fc')
        menubar.add_cascade(label="Outils", menu=tools_menu)

       # Sous-menu Capture d'écran
        capture_menu = tk.Menu(tools_menu, tearoff=0, bg='#161b22', fg='#f0f6fc')
        tools_menu.add_cascade(label="📸 Capture d'écran", menu=capture_menu)
        
        capture_menu.add_command(
            label="🖼️ Capture zone (PNG)", 
            command=self.capturer_zone_screenshot,
            accelerator="Ctrl+Shift+S"
        )
        capture_menu.add_command(
            label="🎬 Capture zone (GIF)", 
            command=self.capturer_zone_gif,
            accelerator="Ctrl+Shift+G"
        )
        capture_menu.add_command(
            label="📽️ Capture zone (Vidéo)", 
            command=self.capturer_zone_video,
            accelerator="Ctrl+Shift+V"
        )
        capture_menu.add_separator()
        capture_menu.add_command(
            label="🪟 Capture fenêtre", 
            command=self.capturer_fenetre
        )
        
        # Ajouter les raccourcis clavier
        self.root.bind('<Control-Shift-S>', lambda e: self.capturer_zone_screenshot())
        self.root.bind('<Control-Shift-G>', lambda e: self.capturer_zone_gif())
        self.root.bind('<Control-Shift-V>', lambda e: self.capturer_zone_video())
    
        # Sous-menu Alignement
        align_menu = tk.Menu(tools_menu, tearoff=0, bg='#161b22', fg='#f0f6fc')
        tools_menu.add_cascade(label="Aligner", menu=align_menu)
        align_menu.add_command(label="Aligner à gauche", command=lambda: self.aligner('gauche'))
        align_menu.add_command(label="Centrer", command=lambda: self.aligner('centre'))
        align_menu.add_command(label="Aligner à droite", command=lambda: self.aligner('droite'))
        align_menu.add_command(label="Aligner en haut", command=lambda: self.aligner('haut'))
        
        tools_menu.add_separator()
        tools_menu.add_checkbutton(label="Grille magnétique", command=self.toggle_magnetisme,
                                  variable=tk.BooleanVar(value=False))
        tools_menu.add_command(label="Valider GitHub", command=self.valider_github)
        
        # Menu Visualisation
        view_menu = tk.Menu(menubar, tearoff=0, bg='#161b22', fg='#f0f6fc')
        menubar.add_cascade(label="Visualisation", menu=view_menu)
        view_menu.add_command(label="Zoom avant", command=self.zoom_avant, accelerator="Ctrl++")
        view_menu.add_command(label="Zoom arrière", command=self.zoom_arriere, accelerator="Ctrl+-")
        view_menu.add_command(label="Réinitialiser zoom", command=self.zoom_reset)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Afficher la grille", command=self.toggle_grille,
                                 variable=tk.BooleanVar(value=True))
        
        # Menu Aide
        help_menu = tk.Menu(menubar, tearoff=0, bg='#161b22', fg='#f0f6fc')
        menubar.add_cascade(label="Aide", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self.afficher_documentation)
        help_menu.add_command(label="Raccourcis clavier", command=self.afficher_raccourcis)
        help_menu.add_separator()
        help_menu.add_command(label="À propos", command=self.a_propos)
        
        # Bind des raccourcis clavier
        self.root.bind('<Control-n>', lambda e: self.nouveau_projet())
        self.root.bind('<Control-o>', lambda e: self.ouvrir_projet())
        self.root.bind('<Control-s>', lambda e: self.sauvegarder_projet())
        self.root.bind('<Control-e>', lambda e: self.generer_markdown())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<Control-a>', lambda e: self.tout_selectionner())
        self.root.bind('<Control-c>', lambda e: self.copier_element())
        self.root.bind('<Control-v>', lambda e: self.coller())
        self.root.bind('<Control-x>', lambda e: self.couper())
        self.root.bind('<Control-plus>', lambda e: self.zoom_avant())
        self.root.bind('<Control-minus>', lambda e: self.zoom_arriere())
    
    def creer_interface(self):
        # === SECTION 1: HEADER (en haut) ===
        header = tk.Frame(self.root, bg='#161b22', height=70)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        tk.Label(header, text="🎨 Éditeur WYSIWYG README Pro - Undo/Redo + Validation GitHub + Tableaux", 
                font=('Segoe UI', 16, 'bold'), bg='#161b22', fg='#f0f6fc').pack(pady=10)
        
        # === SECTION 2: TOOLBAR (sous le header) ===
        toolbar = tk.Frame(self.root, bg='#21262d', height=40)
        toolbar.pack(fill='x', side='top', padx=10, pady=5)
        
        # Undo/Redo
        tk.Button(toolbar, text="↩️ Undo (Ctrl+Z)", command=self.undo,
                 bg='#21262d', fg='#f0f6fc', font=('Segoe UI', 9, 'bold'),
                 relief='flat').pack(side='left', padx=5)
        
        tk.Button(toolbar, text="↪️ Redo (Ctrl+Y)", command=self.redo,
                 bg='#21262d', fg='#f0f6fc', font=('Segoe UI', 9, 'bold'),
                 relief='flat').pack(side='left', padx=5)
        
        tk.Button(toolbar, text="📋 Dupliquer (Ctrl+D)", command=self.dupliquer,
                 bg='#21262d', fg='#f0f6fc', font=('Segoe UI', 9, 'bold'),
                 relief='flat').pack(side='left', padx=5)
        
        tk.Button(toolbar, text="🧲 Grille", command=self.toggle_magnetisme,
                 bg='#21262d', fg='#f0f6fc', font=('Segoe UI', 9, 'bold'),
                 relief='flat').pack(side='left', padx=20)
        
        # Alignement
        tk.Label(toolbar, text="Aligner:", bg='#21262d', fg='#8b949e').pack(side='left', padx=(20,5))
        for dir, icon in [('gauche', '⬅️'), ('centre', '↔️'), ('droite', '➡️'), ('haut', '⬆️')]:
            tk.Button(toolbar, text=f"{icon} {dir}", 
                     command=lambda d=dir: self.aligner(d),
                     bg='#21262d', fg='#f0f6fc', font=('Segoe UI', 9),
                     relief='flat').pack(side='left', padx=2)

        # Frame pour regrouper les boutons de capture
        capture_frame = tk.Frame(toolbar, bg='#21262d')
        capture_frame.pack(side='left', padx=20)

        # Créer le menu
        capture_menu = Menu(capture_frame, tearoff=0, bg='#161b22', fg='#f0f6fc')
        capture_menu.add_command(label="🖼  Capture PNG", command=self.capturer_zone_screenshot)
        capture_menu.add_command(label="🎬  Capture GIF", command=self.capturer_zone_gif)
        capture_menu.add_command(label="📽  Capture Vidéo", command=self.capturer_zone_video)
        capture_menu.add_separator()
        capture_menu.add_command(label="🪟    Capture fenêtre", command=self.capturer_fenetre)

        def show_menu(event):
            capture_menu.post(event.x_root, event.y_root)
        
        # Petit bouton pour le menu déroulant (▼)
        menu_btn = tk.Button(capture_frame, text="📸 Capture ▼", 
                            bg='#21262d', fg='#f78166',
                            font=('Segoe UI', 9, 'bold'),
                            relief='flat', cursor='hand2',
                            padx=5)
        menu_btn.pack(side='left')

        # Lier le clic sur le bouton menu pour afficher le menu
        menu_btn.bind('<Button-1>', show_menu)


        # === SECTION 3: CONTENU PRINCIPAL (prend tout l'espace restant) ===
        main_content = tk.Frame(self.root, bg='#0d1117')
        main_content.pack(fill='both', expand=True, side='top', padx=10, pady=5)
        
        # Diviser le contenu principal en gauche/droite
        left_frame = tk.Frame(main_content, bg='#0d1117')
        left_frame.pack(side='left', fill='both', expand=True)
        
        right_frame = tk.Frame(main_content, bg='#0d1117', width=550)
        right_frame.pack(side='right', fill='both', padx=(10, 0))
        right_frame.pack_propagate(False)
        
        # --- PARTIE GAUCHE : Canvas ---
        # Toolbar éléments
        elem_toolbar = tk.Frame(left_frame, bg='#161b22', height=50)
        elem_toolbar.pack(fill='x', pady=(0, 5))
        
        boutons = [
            ("🎨 Bannière", lambda: self.canvas_editor.ajouter_element('banniere', texte='Mon Projet'), '#238636'),
            ("🎯 Logo", lambda: self.canvas_editor.ajouter_element('logo', texte='MP'), '#1f6feb'),
            ("🎬 GIF", lambda: self.canvas_editor.ajouter_element('gif'), '#8957e5'),
            ("📸 Screenshot", lambda: self.canvas_editor.ajouter_element('screenshot', description='Screenshot'), '#d29922'),
            ("🏷️ Badge", lambda: self.canvas_editor.ajouter_element('badge', texte='v1.0.0', couleur='green'), '#58a6ff'),
            ("📝 Texte", lambda: self.canvas_editor.ajouter_element('texte', texte='Description...'), '#8b949e'),
        ]
        
        for text, cmd, color in boutons:
            tk.Button(elem_toolbar, text=text, command=cmd, bg='#161b22', fg=color,
                     font=('Segoe UI', 9, 'bold'), relief='flat', cursor='hand2',
                     padx=10).pack(side='left', padx=5, pady=5)
        
        tk.Button(elem_toolbar, text="🗑️ Suppr (Del)", command=self.supprimer_selection,
                 bg='#da3633', fg='white', font=('Segoe UI', 9, 'bold'),
                 relief='flat').pack(side='right', padx=10, pady=5)
        
        # Canvas avec scrollbars
        canvas_container = tk.Frame(left_frame, bg='#0d1117')
        canvas_container.pack(fill='both', expand=True)
        
        # Scrollbars
        h_scrollbar = tk.Scrollbar(canvas_container, orient='horizontal', bg='#21262d')
        v_scrollbar = tk.Scrollbar(canvas_container, orient='vertical', bg='#21262d')
        
        # Canvas
        self.canvas_editor = EditeurVisuel(canvas_container)
        self.canvas_editor.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        self.canvas_editor.app = self
        
        # Configuration des scrollbars
        h_scrollbar.config(command=self.canvas_editor.xview)
        v_scrollbar.config(command=self.canvas_editor.yview)
        
        # Placement
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        self.canvas_editor.pack(side='left', fill='both', expand=True)
        
        # Configurer la zone de défilement
        self.canvas_editor.config(scrollregion=(0, 0, 1200, 900))
        
        # Instructions
        tk.Label(left_frame, 
                text="💡 Cliquez sur un élément pour voir les poignées • Drag & drop • Poignées pour resize • Double-clic pour éditer", 
                font=('Segoe UI', 9), bg='#0d1117', fg='#8b949e').pack(pady=5)
        
        # --- PARTIE DROITE : Notebook ---
        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill='both', expand=True)
        
        # Onglet Propriétés
        tab_props = tk.Frame(notebook, bg='#0d1117')
        notebook.add(tab_props, text="⚙️ Propriétés")
        
        # Panneau des propriétés avec scrollbar
        props_canvas = tk.Canvas(tab_props, bg='#0d1117', highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_props, orient="vertical", command=props_canvas.yview)
        scrollable_frame = tk.Frame(props_canvas, bg='#0d1117')
        
        scrollable_frame.bind("<Configure>", lambda e: props_canvas.configure(scrollregion=props_canvas.bbox("all")))
        props_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=530)
        props_canvas.configure(yscrollcommand=scrollbar.set)
        
        tk.Label(scrollable_frame, text="📋 Informations du projet", font=('Segoe UI', 12, 'bold'),
                bg='#0d1117', fg='#f0f6fc').pack(anchor='w', padx=20, pady=10)
        
        self.props = {}
        champs = [
            ('titre', 'Titre du projet', 'Mon Super Projet'),
            ('description', 'Description', 'Une description courte...'),
            ('auteur', 'Auteur', 'Votre Nom'),
            ('github', 'Username GitHub', 'username'),
            ('repo', 'Nom du repo', 'mon-repo'),
        ]
        
        for key, label, default in champs:
            tk.Label(scrollable_frame, text=label, font=('Segoe UI', 10), bg='#0d1117', fg='#8b949e').pack(anchor='w', padx=20)
            var = tk.StringVar(value=default)
            self.props[key] = var
            tk.Entry(scrollable_frame, textvariable=var, font=('Consolas', 11),
                    bg='#21262d', fg='#f0f6fc', relief='flat').pack(fill='x', padx=20, pady=2)
        
        props_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Onglet Markdown
        tab_md = tk.Frame(notebook, bg='#0d1117')
        notebook.add(tab_md, text="📝 Markdown")
        
        frame_md = tk.Frame(tab_md, bg='#0d1117')
        frame_md.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.var_tableau = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_md, text="Exporter en tableau Markdown (pour aligner images)", 
                      variable=self.var_tableau, bg='#0d1117', fg='#f0f6fc',
                      selectcolor='#238636').pack(anchor='w', pady=(0,5))
        
        self.text_md = scrolledtext.ScrolledText(frame_md, font=('Consolas', 10),
                                                bg='#161b22', fg='#f0f6fc', wrap='word', height=20)
        self.text_md.pack(fill='both', expand=True)

        self.text_md.bind('<KeyRelease>', self.mettre_a_jour_apercu_temps_reel)

        # Onglet Validation GitHub
        tab_valid = tk.Frame(notebook, bg='#0d1117')
        notebook.add(tab_valid, text="✅ Validation GitHub")
        
        self.text_validation = scrolledtext.ScrolledText(tab_valid, font=('Consolas', 10),
                                                        bg='#161b22', fg='#f0f6fc', wrap='word')
        self.text_validation.pack(fill='both', expand=True, padx=10, pady=10)
        self.text_validation.insert('1.0', "Cliquez sur 'Générer' pour valider votre README...")
        
        # Onglet Aperçu Réaliste
        tab_preview = tk.Frame(notebook, bg='#0d1117')
        notebook.add(tab_preview, text="👁️ Aperçu GitHub")
        
        preview_frame = tk.Frame(tab_preview, bg='#0d1117')
        preview_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header style GitHub
        preview_header = tk.Frame(preview_frame, bg='#161b22', height=40)
        preview_header.pack(fill='x')
        tk.Label(preview_header, text="README.md", font=('Segoe UI', 11), 
                bg='#161b22', fg='#f0f6fc').pack(anchor='w', padx=10, pady=8)
        
        # Zone de contenu avec fond blanc
        self.preview_container = tk.Frame(preview_frame, bg='#ffffff')
        self.preview_container.pack(fill='both', expand=True)
        
        self.text_apercu = tk.Text(self.preview_container, font=('Segoe UI', 11),
                                  bg='#ffffff', fg='#24292f', wrap='word',
                                  padx=20, pady=20)
        self.text_apercu.pack(fill='both', expand=True)
        self.text_apercu.config(state='disabled')
        
        # === SECTION 4: BARRE DE BOUTONS (EN BAS, TOUJOURS VISIBLE) ===
        bottom_bar = tk.Frame(self.root, bg='#161b22', height=80)
        bottom_bar.pack(fill='x', side='bottom', before=main_content)  # Force la position en bas
        bottom_bar.pack_propagate(False)
        
        # Frame pour centrer les boutons
        button_frame = tk.Frame(bottom_bar, bg='#161b22')
        button_frame.pack(expand=True, fill='both')
        
        # Style des boutons
        btn_style = {
            'font': ('Segoe UI', 12, 'bold'),
            'relief': 'flat',
            'padx': 30,
            'pady': 15,
            'cursor': 'hand2',
            'borderwidth': 0
        }
        
        # Boutons avec couleurs vives
        tk.Button(button_frame, text="🔄 GÉNÉRER", command=self.generer_markdown,
                 bg='#1f6feb', fg='white', **btn_style).pack(side='left', padx=10)
        
        tk.Button(button_frame, text="💾 SAUVEGARDER", command=self.sauvegarder,
                 bg='#238636', fg='white', **btn_style).pack(side='left', padx=10)
        
        tk.Button(button_frame, text="📋 COPIER", command=self.copier,
                 bg='#8957e5', fg='white', **btn_style).pack(side='left', padx=10)
        
        tk.Button(button_frame, text="🧹 NOUVEAU", command=self.nouveau_projet,
                 bg='#da3633', fg='white', **btn_style).pack(side='left', padx=10)

        tk.Button(button_frame, text="🧹 OUVRIR PROJET", command=self.ouvrir_projet,
                 bg='#da3633', fg='white', **btn_style).pack(side='left', padx=10)
        
        tk.Button(button_frame, text="🧹 SAUVEGARDER PROJET", command=self.sauvegarder_projet,
                 bg='#da3633', fg='white', **btn_style).pack(side='left', padx=10)
        
        # Éléments par défaut
        self.ajouter_elements_defaut()
    
    def creer_panneau_proprietes(self, parent):
        canvas = tk.Canvas(parent, bg='#0d1117', highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg='#0d1117')
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw", width=530)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        tk.Label(frame, text="📋 Informations du projet", font=('Segoe UI', 12, 'bold'),
                bg='#0d1117', fg='#f0f6fc').pack(anchor='w', padx=20, pady=10)
        
        self.props = {}
        champs = [
            ('titre', 'Titre du projet', 'Mon Super Projet'),
            ('description', 'Description', 'Une description courte...'),
            ('auteur', 'Auteur', 'Votre Nom'),
            ('github', 'Username GitHub', 'username'),
            ('repo', 'Nom du repo', 'mon-repo'),
        ]
        
        for key, label, default in champs:
            tk.Label(frame, text=label, font=('Segoe UI', 10), bg='#0d1117', fg='#8b949e').pack(anchor='w', padx=20)
            var = tk.StringVar(value=default)
            self.props[key] = var
            tk.Entry(frame, textvariable=var, font=('Consolas', 11),
                    bg='#21262d', fg='#f0f6fc', relief='flat').pack(fill='x', padx=20, pady=2)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def creer_panneau_validation(self, parent):
        """Panneau de validation GitHub"""
        self.text_validation = scrolledtext.ScrolledText(parent, font=('Consolas', 10),
                                                        bg='#161b22', fg='#f0f6fc', wrap='word')
        self.text_validation.pack(fill='both', expand=True, padx=10, pady=10)
        self.text_validation.insert('1.0', "Cliquez sur 'Générer' pour valider votre README...")
    
    def creer_panneau_apercu(self, parent):
        """Panneau d'aperçu réaliste GitHub"""
        # Simuler le rendu GitHub avec un style sombre
        frame = tk.Frame(parent, bg='#0d1117')
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header style GitHub
        header = tk.Frame(frame, bg='#161b22', height=40)
        header.pack(fill='x')
        tk.Label(header, text="README.md", font=('Segoe UI', 11), 
                bg='#161b22', fg='#f0f6fc').pack(anchor='w', padx=10, pady=8)
        
        # Zone de contenu avec fond blanc (comme GitHub)
        self.preview_container = tk.Frame(frame, bg='#ffffff')
        self.preview_container.pack(fill='both', expand=True)
        
        self.text_apercu = tk.Text(self.preview_container, font=('Segoe UI', 11),
                                  bg='#ffffff', fg='#24292f', wrap='word',
                                  padx=20, pady=20)
        self.text_apercu.pack(fill='both', expand=True)
        self.text_apercu.config(state='disabled')
    
    def ajouter_elements_defaut(self):
        self.canvas_editor.ajouter_element('banniere', texte='Mon Super Projet')
        self.canvas_editor.ajouter_element('logo', texte='MP')
        self.canvas_editor.ajouter_element('gif')
        self.canvas_editor.ajouter_element('badge', texte='v1.0.0', couleur='green')
        self.canvas_editor.ajouter_element('badge', texte='Python', couleur='blue')
        self.canvas_editor.ajouter_element('badge', texte='MIT', couleur='yellow')
    
    def undo(self):
        self.canvas_editor.undo()
    
    def redo(self):
        self.canvas_editor.redo()
    
    def dupliquer(self):
        self.canvas_editor.dupliquer()
    
    def toggle_magnetisme(self):
        actif = self.canvas_editor.toggle_magnetisme()
        message = "Grille magnétique ACTIVE" if actif else "Grille magnétique DÉSACTIVÉE"
        # Vous pouvez ajouter un indicateur visuel ici
    
    def aligner(self, direction):
        self.canvas_editor.aligner_elements(direction)
    
    def supprimer_selection(self):
        self.canvas_editor.on_delete(None)
    
    def generer_markdown(self):
        # Générer le markdown
        md = self.canvas_editor.exporter_markdown(tableau=self.var_tableau.get())
        
        # En-tête avec métadonnées
        header = f"<!-- README généré le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\\n\\n"
        header += f"<div align='center'>\\n\\n"
        header += f"# {self.props['titre'].get()}\\n\\n"
        header += f"{self.props['description'].get()}\\n\\n"
        
        # Badges
        github = self.props['github'].get()
        repo = self.props['repo'].get()
        if github != 'username':
            header += f"![Stars](https://img.shields.io/github/stars/{github}/{repo}?style=social) "
        header += f"![Version](https://img.shields.io/badge/version-1.0.0-green) "
        header += f"![License](https://img.shields.io/badge/License-MIT-blue)\\n\\n"
        
        header += """<p align='center'>
  <a href='#-installation'>Installation</a> •
  <a href='#-utilisation'>Utilisation</a>
</p>

</div>

---\\n\\n"""
        
        # Corps
        body = md.replace("<div align='center'>\\n\\n", "").replace("</div>", "")
        
        # Footer
        footer = "\\n\\n---\\n\\n<div align='center'>\\n\\n"
        footer += "⭐ **Star ce repo si vous l'aimez !** 🙏\\n\\n"
        footer += f"Fait avec ❤️ par {self.props['auteur'].get()}\\n\\n"
        footer += "</div>"
        
        complet = header + body + footer
        
        # Afficher markdown
        self.text_md.delete('1.0', 'end')
        self.text_md.insert('1.0', complet)
        self.mettre_a_jour_apercu_temps_reel()
    
        # Valider pour GitHub
        validation = ValidateurGitHub.valider(complet)
        
        # Afficher validation
        self.text_validation.delete('1.0', 'end')
        resultat = f"📊 SCORE DE COMPATIBILITÉ GITHUB: {validation['score']}/100\\n"
        resultat += "="*50 + "\\n\\n"
        
        if validation['valide']:
            resultat += "✅ README compatible GitHub !\\n\\n"
        else:
            resultat += "❌ PROBLÈMES DÉTECTÉS:\\n\\n"
        
        for erreur in validation['erreurs']:
            resultat += f"{erreur}\\n"
        
        if validation['avertissements']:
            resultat += "\\n⚠️ AVERTISSEMENTS:\\n\\n"
            for avert in validation['avertissements']:
                resultat += f"{avert}\\n"
        
        self.text_validation.insert('1.0', resultat)
        
        # Aperçu réaliste (simplifié)
        self.text_apercu.config(state='normal')
        self.text_apercu.delete('1.0', 'end')
        
        # Simuler le rendu markdown basique
        apercu = self.simuler_rendu_github(complet)
        self.text_apercu.insert('1.0', apercu)
        self.text_apercu.config(state='disabled')
    
    def simuler_rendu_github(self, markdown):
        """Simule le rendu GitHub de façon plus fidèle"""
        
        # Créer un texte formaté pour l'aperçu
        texte = markdown
        
        # Nettoyer les balises HTML complexes mais garder la structure
        texte = re.sub(r'<div[^>]*>', '\n', texte)
        texte = texte.replace('</div>', '\n')
        
        # Convertir les images
        def remplacer_image(match):
            url = match.group(1)
            alt = match.group(2) if len(match.groups()) > 1 else "Image"
            width = match.group(3) if len(match.groups()) > 2 else ""
            
            if width:
                return f"\n[🖼️ {alt}] (largeur: {width})\n"
            else:
                return f"\n[🖼️ {alt}]\n"
        
        # Remplacer les balises img
        texte = re.sub(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']+)["\'][^>]*>', 
                       r'\n[🖼️ \2]\n', texte)
        texte = re.sub(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>', 
                       r'\n[🖼️ Image]\n', texte)
        
        # Remplacer les balises de badge
        texte = re.sub(r'<img[^>]*src=["\']https://img\.shields\.io[^>]+>', 
                       r' [📛 Badge] ', texte)
        
        # Convertir les titres
        texte = re.sub(r'^# (.+)$', r'\n\1\n' + '─'*40, texte, flags=re.MULTILINE)
        texte = re.sub(r'^## (.+)$', r'\n\1\n' + '─'*30, texte, flags=re.MULTILINE)
        texte = re.sub(r'^### (.+)$', r'\n\1\n', texte, flags=re.MULTILINE)
        
        # Simuler le HTML inline
        texte = re.sub(r'<br>', '\n', texte)
        texte = re.sub(r'<[^>]+>', '', texte)  # Enlever les autres balises
        
        return texte
    
    def sauvegarder(self):
        content = self.text_md.get('1.0', 'end')
        if not content.strip():
            messagebox.showwarning("Attention", "Générez d'abord le markdown")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
            initialfile="README.md"
        )
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("✅ Succès", f"README sauvegardé:\\n{filepath}")
    
    def copier(self):
        content = self.text_md.get('1.0', 'end')
        if not content.strip():
            messagebox.showwarning("Attention", "Générez d'abord le markdown")
            return
        
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("✅ Copié !", "Contenu copié !")

    def nouveau_projet(self):
        """Crée un nouveau projet"""
        if messagebox.askyesno("Nouveau projet", "Voulez-vous créer un nouveau projet ? Les modifications non sauvegardées seront perdues."):
            # Réinitialiser le canvas
            for elem in self.canvas_editor.elements[:]:
                elem.supprimer()
            self.canvas_editor.elements = []
            self.canvas_editor.element_selectionne = None
            
            # Réinitialiser les propriétés
            for key, var in self.props.items():
                var.set('')
            
            # Ajouter éléments par défaut
            self.ajouter_elements_defaut()
            
            # Vider les zones de texte
            self.text_md.delete('1.0', 'end')
            self.text_validation.delete('1.0', 'end')

    def ouvrir_projet(self):
        """Ouvre un projet sauvegardé"""
        filepath = filedialog.askopenfilename(
            filetypes=[("Projet README", "*.rproj"), ("JSON", "*.json")]
        )
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Réinitialiser
                self.nouveau_projet()
                
                # Restaurer les propriétés
                if 'proprietes' in data:
                    for key, value in data['proprietes'].items():
                        if key in self.props:
                            self.props[key].set(value)
                
                # Restaurer les éléments
                if 'elements' in data:
                    for elem_data in data['elements']:
                        elem = self.canvas_editor.ajouter_element(
                            elem_data['type'],
                            **elem_data.get('kwargs', {})
                        )
                        if elem_data.get('w'): elem.w = elem_data['w']
                        if elem_data.get('h'): elem.h = elem_data['h']
                        if elem_data.get('r'): elem.r = elem_data['r']
                        elem.x, elem.y = elem_data['x'], elem_data['y']
                        
                        # Déplacer à la bonne position
                        for item in elem.items:
                            self.canvas_editor.coords(item, 
                                self.canvas_editor.coords(item)[0] + elem.x - 100,
                                self.canvas_editor.coords(item)[1] + elem.y - 50)
                
                messagebox.showinfo("Succès", "Projet chargé avec succès !")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de charger le projet : {str(e)}")

    def sauvegarder_projet(self):
        """Sauvegarde le projet"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".rproj",
            filetypes=[("Projet README", "*.rproj"), ("JSON", "*.json")]
        )
        if filepath:
            try:
                data = {
                    'proprietes': {k: v.get() for k, v in self.props.items()},
                    'elements': [elem.to_dict() for elem in self.canvas_editor.elements],
                    'version': '1.0'
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Succès", "Projet sauvegardé avec succès !")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de sauvegarder : {str(e)}")

    def exporter_html(self):
        """Exporte en HTML"""
        md_content = self.text_md.get('1.0', 'end-1c')
        if not md_content.strip():
            messagebox.showwarning("Attention", "Générez d'abord le markdown")
            return
        
        html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>README</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; }}
            img {{ max-width: 100%; }}
        </style>
    </head>
    <body>
        {md_content}
    </body>
    </html>"""
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML", "*.html")]
        )
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            messagebox.showinfo("Succès", "HTML exporté avec succès !")

    def couper(self):
        """Coupe l'élément sélectionné"""
        self.copier_element()
        self.supprimer_selection()

    def copier_element(self):
        """Copie l'élément sélectionné dans le presse-papiers interne"""
        if self.canvas_editor.element_selectionne:
            data = self.canvas_editor.element_selectionne.to_dict()
            self.root.clipboard_clear()
            self.root.clipboard_append(json.dumps(data))
            self.copied_element = data
        else:
            messagebox.showinfo("Info", "Aucun élément sélectionné à copier")

    def coller(self):
        """Colle l'élément copié"""
        try:
            data_str = self.root.clipboard_get()
            data = json.loads(data_str)
            
            if isinstance(data, dict) and 'type' in data:
                # Décaler un peu pour éviter la superposition
                data['x'] += 30
                data['y'] += 30
                
                elem = self.canvas_editor.ajouter_element(
                    data['type'],
                    **data.get('kwargs', {})
                )
                if data.get('w'): elem.w = data['w']
                if data.get('h'): elem.h = data['h']
                if data.get('r'): elem.r = data['r']
                elem.x, elem.y = data['x'], data['y']
                
                # Déplacer à la bonne position
                for item in elem.items:
                    self.canvas_editor.coords(item, 
                        self.canvas_editor.coords(item)[0] + data['x'] - 100,
                        self.canvas_editor.coords(item)[1] + data['y'] - 50)
                
                self.canvas_editor.selectionner_element(elem)
                elem.selectionner()
        except:
            pass

    def tout_selectionner(self):
        """Sélectionne tous les éléments"""
        for elem in self.canvas_editor.elements:
            elem.selectionner()
            self.canvas_editor.element_selectionne = elem  # Garde le dernier sélectionné

    def valider_github(self):
        """Valide directement sans générer"""
        content = self.text_md.get('1.0', 'end-1c')  # ← Utiliser 'end-1c' au lieu de 'end'
        if not content.strip():
            messagebox.showwarning("Attention", "Générez d'abord le markdown")
            return
        
        validation = ValidateurGitHub.valider(content)
        self.text_validation.delete('1.0', 'end')
        resultat = f"📊 SCORE: {validation['score']}/100\n\n"
        
        if validation['erreurs']:
            resultat += "❌ ERREURS:\n"
            for erreur in validation['erreurs']:
                resultat += f"{erreur}\n"
        
        if validation['avertissements']:
            resultat += "\n⚠️ AVERTISSEMENTS:\n"
            for avert in validation['avertissements']:
                resultat += f"{avert}\n"
        
        if not validation['erreurs'] and not validation['avertissements']:
            resultat += "✅ Aucun problème détecté !"
        
        self.text_validation.insert('1.0', resultat)

    def zoom_avant(self):
        """Zoom avant sur le canvas"""
        # Obtenir le centre actuel du canvas visible
        bbox = self.canvas_editor.bbox("all")
        if bbox:
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
        else:
            center_x, center_y = 440, 350
        
        # Appliquer le zoom
        self.canvas_editor.scale("all", center_x, center_y, 1.1, 1.1)
        self.canvas_editor.zoom_factor *= 1.1

    def zoom_arriere(self):
        """Zoom arrière sur le canvas"""
        # Obtenir le centre actuel du canvas visible
        bbox = self.canvas_editor.bbox("all")
        if bbox:
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
        else:
            center_x, center_y = 440, 350
        
        # Appliquer le zoom arrière
        self.canvas_editor.scale("all", center_x, center_y, 0.9, 0.9)
        self.canvas_editor.zoom_factor *= 0.9

    def zoom_reset(self):
        """Réinitialise le zoom"""
        if self.canvas_editor.zoom_factor != 1.0:
            # Calculer le facteur inverse pour revenir à l'échelle 1.0
            factor = 1.0 / self.canvas_editor.zoom_factor
            
            # Obtenir le centre
            bbox = self.canvas_editor.bbox("all")
            if bbox:
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
            else:
                center_x, center_y = 440, 350
            
            # Réinitialiser le zoom
            self.canvas_editor.scale("all", center_x, center_y, factor, factor)
            self.canvas_editor.zoom_factor = 1.0

    def toggle_grille(self):
        """Affiche/masque la grille"""
        if hasattr(self.canvas_editor, 'grille_visible'):
            self.canvas_editor.grille_visible = not self.canvas_editor.grille_visible
            if self.canvas_editor.grille_visible:
                self.canvas_editor.dessiner_grille()
            else:
                self.canvas_editor.delete('grille')
        else:
            self.canvas_editor.grille_visible = True
            self.canvas_editor.dessiner_grille()

    def afficher_documentation(self):
        """Affiche la documentation"""
        doc = tk.Toplevel(self.root)
        doc.title("Documentation")
        doc.geometry("600x400")
        doc.configure(bg='#0d1117')
        
        text = scrolledtext.ScrolledText(doc, bg='#161b22', fg='#f0f6fc',
                                        font=('Segoe UI', 11), wrap='word')
        text.pack(fill='both', expand=True, padx=10, pady=10)
        
        documentation = """
    🎨 ÉDITEUR README PRO - DOCUMENTATION

    📌 ÉLÉMENTS DISPONIBLES:
    • Bannière - En-tête coloré pour votre projet
    • Logo - Cercle avec initiales ou image
    • GIF - Zone pour animations/démonstrations
    • Screenshot - Capture d'écran
    • Badge - Badges de statut (version, licence...)
    • Texte - Texte formatable (gras, italique, listes)

    🖱️ INTERACTION:
    • Glisser-déposer pour positionner
    • Poignées pour redimensionner
    • Double-clic pour éditer
    • Ctrl+Z/Y pour Undo/Redo
    • Ctrl+D pour dupliquer

    ⌨️ RACCOURCIS CLAVIER:
    • Ctrl+N - Nouveau projet
    • Ctrl+O - Ouvrir projet
    • Ctrl+S - Sauvegarder projet
    • Ctrl+E - Exporter Markdown
    • Ctrl+Z - Annuler
    • Ctrl+Y - Rétablir
    • Ctrl+A - Tout sélectionner
    • Ctrl+C - Copier
    • Ctrl+V - Coller
    • Suppr - Supprimer

    ✅ VALIDATION GITHUB:
    L'outil vérifie automatiquement la compatibilité GitHub:
    • Pas de JavaScript ou CSS avancé
    • URLs d'images valides
    • Pas d'iframes ou contenu embarqué
    • Optimisation des GIFs
        """
        text.insert('1.0', documentation)
        text.config(state='disabled')

    def afficher_raccourcis(self):
        """Affiche les raccourcis clavier"""
        shortcuts = tk.Toplevel(self.root)
        shortcuts.title("Raccourcis clavier")
        shortcuts.geometry("400x300")
        shortcuts.configure(bg='#0d1117')
        
        text = tk.Text(shortcuts, bg='#161b22', fg='#f0f6fc', font=('Consolas', 11))
        text.pack(fill='both', expand=True, padx=10, pady=10)
        
        raccourcis = """
    RACCOURCIS CLAVIER:

    📁 Fichier
    Ctrl+N : Nouveau projet
    Ctrl+O : Ouvrir projet
    Ctrl+S : Sauvegarder projet
    Ctrl+E : Exporter Markdown
    Ctrl+Q : Quitter

    ✏️ Édition
    Ctrl+Z : Annuler
    Ctrl+Y : Rétablir
    Ctrl+X : Couper
    Ctrl+C : Copier
    Ctrl+V : Coller
    Ctrl+D : Dupliquer
    Suppr  : Supprimer
    Ctrl+A : Tout sélectionner

    🔍 Visualisation
    Ctrl++ : Zoom avant
    Ctrl+- : Zoom arrière
        """
        text.insert('1.0', raccourcis)
        text.config(state='disabled')

    def a_propos(self):
        """Fenêtre À propos"""
        about = tk.Toplevel(self.root)
        about.title("À propos")
        about.geometry("400x300")
        about.configure(bg='#0d1117')
        
        tk.Label(about, text="🎨 Éditeur WYSIWYG README Pro", 
                font=('Segoe UI', 18, 'bold'), bg='#0d1117', fg='#f0f6fc').pack(pady=20)
        
        tk.Label(about, text="Version 2.0", 
                font=('Segoe UI', 12), bg='#0d1117', fg='#8b949e').pack()
        
        tk.Label(about, text="\nCréez des README magnifiques\npour GitHub avec une interface visuelle",
                font=('Segoe UI', 11), bg='#0d1117', fg='#f0f6fc').pack(pady=10)
        
        tk.Label(about, text="\n© 2026 - Tous droits réservés",
                font=('Segoe UI', 9), bg='#0d1117', fg='#8b949e').pack(side='bottom', pady=10)
        
        tk.Button(about, text="Fermer", command=about.destroy,
                 bg='#238636', fg='white', font=('Segoe UI', 10, 'bold')).pack(pady=20)

    def generer_markdown(self):
        """Génère le markdown à partir de l'état réel du canvas"""
        
        # Récupérer les propriétés du projet
        titre = self.props['titre'].get()
        description = self.props['description'].get()
        auteur = self.props['auteur'].get()
        github = self.props['github'].get()
        repo = self.props['repo'].get()
        
        # Construire l'en-tête
        header = f"<!-- README généré le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n\n"
        header += f"# {titre}\n\n"
        header += f"{description}\n\n"
        
        # Badges de projet
        if github != 'username' and repo != 'mon-repo':
            header += f"<div align='center'>\n\n"
            header += f"![GitHub stars](https://img.shields.io/github/stars/{github}/{repo}?style=social) "
            header += f"![GitHub forks](https://img.shields.io/github/forks/{github}/{repo}?style=social)\n\n"
            header += f"</div>\n\n"
        
        header += "---\n\n"
        
        # Corps - Utiliser l'export du canvas
        body = self.canvas_editor.exporter_markdown(tableau=self.var_tableau.get())
        
        # Pied de page
        footer = "\n\n---\n\n"
        footer += f"<div align='center'>\n\n"
        footer += f"**⭐ Star ce repo si vous l'aimez !** 🙏\n\n"
        footer += f"Fait avec ❤️ par {auteur}\n\n"
        footer += f"</div>"
        
        # Assembler
        complet = header + body + footer
        
        # Afficher dans l'onglet Markdown
        self.text_md.delete('1.0', 'end')
        self.text_md.insert('1.0', complet)
        
        # Valider pour GitHub
        validation = ValidateurGitHub.valider(complet)
        
        # Afficher la validation
        self.text_validation.delete('1.0', 'end')
        resultat = f"📊 SCORE DE COMPATIBILITÉ GITHUB: {validation['score']}/100\n"
        resultat += "="*50 + "\n\n"
        
        if validation['valide']:
            resultat += "✅ README compatible GitHub !\n\n"
        else:
            resultat += "❌ PROBLÈMES DÉTECTÉS:\n\n"
        
        for erreur in validation['erreurs']:
            resultat += f"{erreur}\n"
        
        if validation['avertissements']:
            resultat += "\n⚠️ AVERTISSEMENTS:\n\n"
            for avert in validation['avertissements']:
                resultat += f"{avert}\n"
        
        self.text_validation.insert('1.0', resultat)
        
        # Mettre à jour l'aperçu
        self.mettre_a_jour_apercu(complet)

    def mettre_a_jour_apercu(self, markdown):
        """Met à jour l'aperçu GitHub avec le contenu markdown"""
        self.text_apercu.config(state='normal')
        self.text_apercu.delete('1.0', 'end')
        
        # Simuler le rendu
        apercu = self.simuler_rendu_github(markdown)
        self.text_apercu.insert('1.0', apercu)
        self.text_apercu.config(state='disabled')

    def synchroniser_canvas_avec_proprietes(self):
        """Met à jour les éléments du canvas avec les propriétés du projet"""
        for elem in self.canvas_editor.elements:
            if elem.type == 'banniere':
                elem.kwargs['texte'] = self.props['titre'].get()
                if hasattr(elem, 'text_item'):
                    self.canvas_editor.itemconfig(elem.text_item, text=elem.kwargs['texte'])

    def choisir_image_locale(self):
        """Ouvre une boîte de dialogue pour choisir une image locale"""
        filepath = filedialog.askopenfilename(
            title="Choisir une image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.svg *.webp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("GIF", "*.gif"),
                ("SVG", "*.svg"),
                ("WEBP", "*.webp"),
                ("Tous les fichiers", "*.*")
            ]
        )
        
        if filepath:
            # Créer le dossier 'images' s'il n'existe pas
            images_dir = Path.cwd() / "images"
            images_dir.mkdir(exist_ok=True)
            
            # Copier l'image dans le dossier 'images'
            import shutil
            filename = Path(filepath).name
            destination = images_dir / filename
            
            # Éviter les doublons
            counter = 1
            while destination.exists():
                name_without_ext = Path(filepath).stem
                ext = Path(filepath).suffix
                destination = images_dir / f"{name_without_ext}_{counter}{ext}"
                counter += 1
            
            try:
                shutil.copy2(filepath, destination)
                # Retourner le chemin relatif
                return f"images/{destination.name}"
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de copier l'image : {str(e)}")
                return None
        
        return None

    def ouvrir_dossier_images(self):
        """Ouvre le dossier images dans l'explorateur de fichiers"""
        images_dir = Path.cwd() / "images"
        images_dir.mkdir(exist_ok=True)
        
        import os
        import platform
        
        if platform.system() == "Windows":
            os.startfile(images_dir)
        elif platform.system() == "Darwin":  # macOS
            os.system(f"open {images_dir}")
        else:  # Linux
            os.system(f"xdg-open {images_dir}")

    def capturer_zone_screenshot(self):
        """Capture une zone en screenshot"""
        if not hasattr(self, 'outil_capture'):
            self.outil_capture = OutilCapture(self)
        self.outil_capture.capturer_zone('screenshot')

    def capturer_zone_gif(self):
        """Capture une zone en GIF animé"""
        if not hasattr(self, 'outil_capture'):
            self.outil_capture = OutilCapture(self)
        self.outil_capture.capturer_zone('gif')

    def capturer_zone_video(self):
        """Capture une zone en vidéo"""
        if not hasattr(self, 'outil_capture'):
            self.outil_capture = OutilCapture(self)
        self.outil_capture.capturer_zone('video')

    def capturer_fenetre(self):
        """Capture une fenêtre spécifique"""
        # Liste des fenêtres ouvertes
        import win32gui
        import win32con
        
        def enum_window_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                windows.append((hwnd, win32gui.GetWindowText(hwnd)))
        
        windows = []
        win32gui.EnumWindows(enum_window_callback, windows)
        
        # Créer un dialogue de sélection
        dialog = tk.Toplevel(self.root)
        dialog.title("Choisir une fenêtre")
        dialog.geometry("500x400")
        dialog.configure(bg='#161b22')
        
        tk.Label(dialog, text="Sélectionnez une fenêtre à capturer:",
                font=('Segoe UI', 12, 'bold'), bg='#161b22', fg='#f0f6fc').pack(pady=10)
        
        listbox = tk.Listbox(dialog, bg='#0d1117', fg='#f0f6fc', font=('Consolas', 10))
        listbox.pack(fill='both', expand=True, padx=10, pady=10)
        
        for hwnd, title in windows:
            listbox.insert('end', f"{title[:50]}...")
        
        def capturer():
            selection = listbox.curselection()
            if selection:
                hwnd, title = windows[selection[0]]
                
                # Obtenir les dimensions de la fenêtre
                rect = win32gui.GetWindowRect(hwnd)
                x1, y1, x2, y2 = rect
                
                # Capturer
                screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                
                # Sauvegarder
                images_dir = Path.cwd() / "images"
                images_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = images_dir / f"fenetre_{timestamp}.png"
                screenshot.save(filename)
                
                messagebox.showinfo("Succès", f"Fenêtre capturée :\n{filename}")
                
                if messagebox.askyesno("Ajouter", "Ajouter cette image au canvas ?"):
                    self.canvas_editor.ajouter_element('screenshot', url=str(filename))
                
                dialog.destroy()
        
        tk.Button(dialog, text="Capturer", command=capturer,
                 bg='#238636', fg='white', font=('Segoe UI', 11, 'bold')).pack(pady=10)

    def markdown_vers_html(self, markdown_texte):
        """Convertit le markdown en HTML avec style GitHub"""
        
        # Configuration des extensions pour un rendu GitHub-like
        extensions = [
            'markdown.extensions.extra',
            'markdown.extensions.codehilite',
            'markdown.extensions.tables',
            'markdown.extensions.toc',
            'markdown.extensions.nl2br',
            'markdown.extensions.sane_lists',
            'markdown.extensions.smarty',
            'pymdownx.tasklist',
            'pymdownx.emoji',
        ]
        
        # Options pour les extensions
        extension_configs = {
            'codehilite': {
                'linenums': False,
                'guess_lang': True,
                'use_pygments': True,
                'noclasses': False,
            },
            'pymdownx.tasklist': {
                'custom_checkbox': True,
            },
        }
        
        # Convertir le markdown en HTML
        html = markdown.markdown(
            markdown_texte,
            extensions=extensions,
            extension_configs=extension_configs
        )
        
        return html

    def generer_apercu_html(self, markdown_texte):
        """Génère un HTML complet avec style GitHub"""
        
        html_content = self.markdown_vers_html(markdown_texte)
        
        # Style GitHub complet
        github_style = """
        <style>
            /* GitHub Markdown CSS */
            .markdown-body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                font-size: 16px;
                line-height: 1.6;
                word-wrap: break-word;
                color: #24292f;
                background-color: #ffffff;
                padding: 45px;
                max-width: 980px;
                margin: 0 auto;
            }
            
            .markdown-body h1, .markdown-body h2, .markdown-body h3 {
                margin-top: 24px;
                margin-bottom: 16px;
                font-weight: 600;
                line-height: 1.25;
            }
            
            .markdown-body h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
            .markdown-body h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
            .markdown-body h3 { font-size: 1.25em; }
            
            .markdown-body p { margin-top: 0; margin-bottom: 16px; }
            
            .markdown-body a { color: #0969da; text-decoration: none; }
            .markdown-body a:hover { text-decoration: underline; }
            
            .markdown-body img { max-width: 100%; box-sizing: content-box; }
            
            .markdown-body pre {
                padding: 16px;
                overflow: auto;
                font-size: 85%;
                line-height: 1.45;
                background-color: #f6f8fa;
                border-radius: 6px;
            }
            
            .markdown-body code {
                padding: 0.2em 0.4em;
                margin: 0;
                font-size: 85%;
                background-color: #f6f8fa;
                border-radius: 6px;
                font-family: 'SF Mono', Monaco, Consolas, 'Liberation Mono', Courier, monospace;
            }
            
            .markdown-body table {
                display: block;
                width: 100%;
                width: max-content;
                max-width: 100%;
                overflow: auto;
                border-spacing: 0;
                border-collapse: collapse;
            }
            
            .markdown-body table th,
            .markdown-body table td {
                padding: 6px 13px;
                border: 1px solid #d0d7de;
            }
            
            .markdown-body table tr {
                background-color: #ffffff;
                border-top: 1px solid #d0d7de;
            }
            
            .markdown-body table tr:nth-child(2n) {
                background-color: #f6f8fa;
            }
            
            .markdown-body blockquote {
                padding: 0 1em;
                color: #57606a;
                border-left: 0.25em solid #d0d7de;
                margin: 0 0 16px 0;
            }
            
            .markdown-body hr {
                height: 0.25em;
                padding: 0;
                margin: 24px 0;
                background-color: #d0d7de;
                border: 0;
            }
            
            .markdown-body ul, .markdown-body ol {
                padding-left: 2em;
                margin-top: 0;
                margin-bottom: 16px;
            }
            
            .markdown-body li {
                margin-top: 0.25em;
            }
            
            /* Task list items */
            .markdown-body .task-list-item {
                list-style-type: none;
            }
            
            .markdown-body .task-list-item input {
                margin: 0 0.2em 0.25em -1.6em;
                vertical-align: middle;
            }
            
            /* Code highlighting */
            .codehilite .hll { background-color: #f6f8fa; }
            .codehilite .c { color: #6e7781; } /* Comment */
            .codehilite .k { color: #cf222e; } /* Keyword */
            .codehilite .o { color: #0550ae; } /* Operator */
            .codehilite .cm { color: #6e7781; } /* Comment.Multiline */
            .codehilite .cp { color: #bc4c00; } /* Comment.Preproc */
            .codehilite .c1 { color: #6e7781; } /* Comment.Single */
            .codehilite .cs { color: #6e7781; } /* Comment.Special */
            .codehilite .gd { color: #82071e; } /* Generic.Deleted */
            .codehilite .ge { font-style: italic; } /* Generic.Emph */
            .codehilite .gh { color: #0550ae; } /* Generic.Heading */
            .codehilite .gi { color: #116329; } /* Generic.Inserted */
            .codehilite .gp { color: #656d76; } /* Generic.Prompt */
            .codehilite .gs { font-weight: bold; } /* Generic.Strong */
            .codehilite .gu { color: #0550ae; } /* Generic.Subheading */
            .codehilite .kc { color: #cf222e; } /* Keyword.Constant */
            .codehilite .kd { color: #cf222e; } /* Keyword.Declaration */
            .codehilite .kn { color: #cf222e; } /* Keyword.Namespace */
            .codehilite .kp { color: #cf222e; } /* Keyword.Pseudo */
            .codehilite .kr { color: #cf222e; } /* Keyword.Reserved */
            .codehilite .kt { color: #cf222e; } /* Keyword.Type */
            .codehilite .m { color: #0550ae; } /* Number */
            .codehilite .s { color: #0a3069; } /* String */
            .codehilite .na { color: #953800; } /* Name.Attribute */
            .codehilite .nb { color: #953800; } /* Name.Builtin */
            .codehilite .nc { color: #953800; } /* Name.Class */
            .codehilite .no { color: #953800; } /* Name.Constant */
            .codehilite .nd { color: #8250df; } /* Name.Decorator */
            .codehilite .ni { color: #953800; } /* Name.Entity */
            .codehilite .ne { color: #953800; } /* Name.Exception */
            .codehilite .nf { color: #8250df; } /* Name.Function */
            .codehilite .nl { color: #953800; } /* Name.Label */
            .codehilite .nn { color: #953800; } /* Name.Namespace */
            .codehilite .nx { color: #953800; } /* Name.Other */
            .codehilite .py { color: #953800; } /* Name.Property */
            .codehilite .nt { color: #953800; } /* Name.Tag */
            .codehilite .nv { color: #953800; } /* Name.Variable */
            .codehilite .ow { color: #cf222e; } /* Operator.Word */
            .codehilite .w { color: #bbbbbb; } /* Text.Whitespace */
            .codehilite .mb { color: #0550ae; } /* Number.Bin */
            .codehilite .mf { color: #0550ae; } /* Number.Float */
            .codehilite .mh { color: #0550ae; } /* Number.Hex */
            .codehilite .mi { color: #0550ae; } /* Number.Integer */
            .codehilite .mo { color: #0550ae; } /* Number.Oct */
            .codehilite .sb { color: #0a3069; } /* String.Backtick */
            .codehilite .sc { color: #0a3069; } /* String.Char */
            .codehilite .sd { color: #0a3069; } /* String.Doc */
            .codehilite .s2 { color: #0a3069; } /* String.Double */
            .codehilite .se { color: #0a3069; } /* String.Escape */
            .codehilite .sh { color: #0a3069; } /* String.Heredoc */
            .codehilite .si { color: #0a3069; } /* String.Interpol */
            .codehilite .sx { color: #0a3069; } /* String.Other */
            .codehilite .sr { color: #0a3069; } /* String.Regex */
            .codehilite .s1 { color: #0a3069; } /* String.Single */
            .codehilite .ss { color: #0a3069; } /* String.Symbol */
            .codehilite .bp { color: #953800; } /* Name.Builtin.Pseudo */
            .codehilite .vc { color: #953800; } /* Name.Variable.Class */
            .codehilite .vg { color: #953800; } /* Name.Variable.Global */
            .codehilite .vi { color: #953800; } /* Name.Variable.Instance */
            .codehilite .il { color: #0550ae; } /* Number.Integer.Long */
        </style>
        """
        
        # Convertir le markdown en HTML
        html_content = markdown.markdown(
            markdown_texte,
            extensions=extensions,
            extension_configs=extension_configs
        )
        
        # Gérer les chemins d'images locaux
        # Remplacer les chemins relatifs par des chemins absolus pour l'aperçu
        import os
        base_dir = Path.cwd()
        
        def remplacer_chemin_image(match):
            url = match.group(1)
            if url.startswith(('http://', 'https://')):
                return f'src="{url}"'
            else:
                # Construire le chemin absolu
                chemin_absolu = base_dir / url
                if chemin_absolu.exists():
                    return f'src="file:///{chemin_absolu.absolute()}"'
                else:
                    return f'src="{url}" (fichier non trouvé)'
        
        import re
        html_content = re.sub(r'src="([^"]+)"', remplacer_chemin_image, html_content)
        
        # Style GitHub complet (version allégée pour l'intégration)
        github_style = """
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                font-size: 16px;
                line-height: 1.6;
                color: #24292f;
                background-color: #ffffff;
                padding: 20px;
            }
            .markdown-body {
                max-width: 980px;
                margin: 0 auto;
            }
            .markdown-body h1 { 
                font-size: 2em; 
                border-bottom: 1px solid #eaecef; 
                padding-bottom: 0.3em; 
                margin-top: 24px;
                margin-bottom: 16px;
                font-weight: 600;
                line-height: 1.25;
            }
            .markdown-body h2 { 
                font-size: 1.5em; 
                border-bottom: 1px solid #eaecef; 
                padding-bottom: 0.3em; 
                margin-top: 24px;
                margin-bottom: 16px;
                font-weight: 600;
                line-height: 1.25;
            }
            .markdown-body h3 { 
                font-size: 1.25em; 
                margin-top: 24px;
                margin-bottom: 16px;
                font-weight: 600;
                line-height: 1.25;
            }
            .markdown-body p { margin-top: 0; margin-bottom: 16px; }
            .markdown-body a { color: #0969da; text-decoration: none; }
            .markdown-body a:hover { text-decoration: underline; }
            .markdown-body img { max-width: 100%; box-sizing: content-box; }
            .markdown-body pre {
                padding: 16px;
                overflow: auto;
                font-size: 85%;
                line-height: 1.45;
                background-color: #f6f8fa;
                border-radius: 6px;
            }
            .markdown-body code {
                padding: 0.2em 0.4em;
                margin: 0;
                font-size: 85%;
                background-color: #f6f8fa;
                border-radius: 6px;
                font-family: 'SF Mono', Monaco, Consolas, 'Liberation Mono', Courier, monospace;
            }
            .markdown-body pre code {
                padding: 0;
                margin: 0;
                font-size: 100%;
                word-break: normal;
                white-space: pre;
                background: transparent;
                border: 0;
            }
            .markdown-body table {
                display: block;
                width: 100%;
                overflow: auto;
                border-spacing: 0;
                border-collapse: collapse;
                margin-bottom: 16px;
            }
            .markdown-body table th,
            .markdown-body table td {
                padding: 6px 13px;
                border: 1px solid #d0d7de;
            }
            .markdown-body table tr {
                background-color: #ffffff;
                border-top: 1px solid #d0d7de;
            }
            .markdown-body table tr:nth-child(2n) {
                background-color: #f6f8fa;
            }
            .markdown-body blockquote {
                padding: 0 1em;
                color: #57606a;
                border-left: 0.25em solid #d0d7de;
                margin: 0 0 16px 0;
            }
            .markdown-body hr {
                height: 0.25em;
                padding: 0;
                margin: 24px 0;
                background-color: #d0d7de;
                border: 0;
            }
            .markdown-body ul, .markdown-body ol {
                padding-left: 2em;
                margin-top: 0;
                margin-bottom: 16px;
            }
            .markdown-body li {
                margin-top: 0.25em;
            }
            .markdown-body .task-list-item {
                list-style-type: none;
            }
            .markdown-body .task-list-item input {
                margin: 0 0.2em 0.25em -1.6em;
                vertical-align: middle;
            }
        </style>
        """
        
        # Template HTML complet pour l'aperçu intégré
        html_template = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {github_style}
        <base href="file:///{Path.cwd()}/">
    </head>
    <body>
        <div class="markdown-body">
            {html_content}
        </div>
    </body>
    </html>"""
        
        return html_template

    def mettre_a_jour_apercu_temps_reel(self, event=None):
        """Met à jour l'aperçu en temps réel dans l'onglet"""
        markdown_texte = self.text_md.get('1.0', 'end-1c')
        
        if not markdown_texte.strip():
            return
        
        # Générer le HTML
        html = self.generer_apercu_html(markdown_texte)
        
        # Afficher dans l'onglet
        if hasattr(self, 'use_html') and self.use_html and hasattr(self, 'html_frame'):
            # Utiliser HtmlFrame pour un vrai rendu HTML
            self.html_frame.set_content(html)
        else:
            # Fallback sur l'aperçu texte
            self.text_apercu.config(state='normal')
            self.text_apercu.delete('1.0', 'end')
            apercu_simple = self.simuler_rendu_github(markdown_texte)
            self.text_apercu.insert('1.0', apercu_simple)
            self.text_apercu.config(state='disabled')

    def rafraichir_apercu(self):
        """Rafraîchit manuellement l'aperçu"""
        self.mettre_a_jour_apercu_temps_reel()

    def ouvrir_apercu_navigateur(self):
        """Ouvre l'aperçu HTML dans le navigateur par défaut"""
        if not hasattr(self, 'dernier_html') or not self.dernier_html:
            self.generer_markdown()
        
        if hasattr(self, 'dernier_html'):
            # Créer un fichier temporaire
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(self.dernier_html)
                temp_file = f.name
            
            # Ouvrir dans le navigateur
            webbrowser.open('file://' + os.path.abspath(temp_file))
            
            # Optionnel : supprimer le fichier après un délai
            import threading
            def supprimer_fichier():
                import time
                time.sleep(5)
                try:
                    os.unlink(temp_file)
                except:
                    pass
            
            threading.Thread(target=supprimer_fichier, daemon=True).start()

    def creer_panneau_apercu(self, parent):
        """Panneau d'aperçu GitHub avec rendu HTML intégré"""
        frame = tk.Frame(parent, bg='#0d1117')
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Barre d'outils pour l'aperçu
        toolbar = tk.Frame(frame, bg='#161b22', height=35)
        toolbar.pack(fill='x', pady=(0, 5))
        
        tk.Label(toolbar, text="👁️ Aperçu en temps réel", 
                font=('Segoe UI', 10, 'bold'), bg='#161b22', fg='#f0f6fc').pack(side='left', padx=10)
        
        # Bouton pour rafraîchir manuellement
        tk.Button(toolbar, text="🔄 Rafraîchir", command=self.rafraichir_apercu,
                 bg='#21262d', fg='#f0f6fc', font=('Segoe UI', 8),
                 relief='flat').pack(side='right', padx=5)
        
        # Utiliser HtmlFrame pour le rendu HTML
        try:
            from tkinterhtml import HtmlFrame
            self.html_frame = HtmlFrame(frame, horizontal_scrollbar="auto")
            self.html_frame.pack(fill='both', expand=True)
            self.use_html = True
        except ImportError:
            # Fallback si tkinterhtml n'est pas installé
            self.use_html = False
            self.text_apercu = scrolledtext.ScrolledText(
                frame, font=('Consolas', 10), bg='#ffffff', fg='#24292f',
                wrap='word', padx=10, pady=10
            )
            self.text_apercu.pack(fill='both', expand=True)
            self.text_apercu.config(state='disabled')
            
            # Message d'information
            info_label = tk.Label(frame, 
                text="💡 Pour un véritable aperçu HTML, installez tkinterhtml : pip install tkinterhtml",
                bg='#0d1117', fg='#f78166', font=('Segoe UI', 9))
            info_label.pack(pady=5)
        
if __name__ == "__main__":
    root = tk.Tk()
    app = ApplicationPrincipale(root)
    root.mainloop()