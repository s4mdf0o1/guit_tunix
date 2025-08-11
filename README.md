# Guit Tunix

Simple Python guitar tuner

Développé avec l'aide de ChatGPT

utilise la méthode YIN : algorythme de traitement du signal, afin de muter les harmoniques et augmenter la fréquence principale.

## Hardware

Utilisé avec un câble Jack->USB sur Gibson BluesHawk.

modèle détecté :
```
Bus 002 Device 019: ID 0d8c:0008 C-Media Electronics, Inc. C-Media USB Audio Device
```

Fonctionne au micro à la voix (avec quelques difficultés, mais quand même X-) 

## Install
Dans un venv :

```bash
pip install  -r requirements.txt
```

## Screenshot Demo

![Animation du déplacement du curseur et sélection de la note pour accorder la guitare](./snapshot/demo.gif)

## Limitations

Pour l'heure, ne permet d'accorder la guitare qu'en standard E-A-D-G-B-E

