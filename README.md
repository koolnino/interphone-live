# Interphone Live — bêta 0.1.0

Un panneau Home Assistant pour transmettre sa voix depuis le microphone d’un iPhone ou d’un navigateur vers une enceinte ou un groupe Music Assistant. Sens unique : il ne donne pas accès au microphone des enceintes.

## État du projet

Cette version générique est dérivée d’un prototype utilisé sur une installation privée. Elle n’a pas encore été installée et validée dans un Home Assistant vierge. Les tests locaux couvrent le tampon audio, le décodage WAV, la validation des paramètres et les gardes de reprise Spotify simulées. Ils ne prouvent pas la compatibilité de tous les modèles d’enceintes. La reprise Spotify est expérimentale, désactivée par défaut ; elle ne garantit ni la position exacte ni la restauration de la file.

## Prérequis et installation manuelle

1. Home Assistant 2026.10 ou ultérieur (cible initiale, matrice de versions restant à vérifier), intégration Music Assistant configurée et action `music_assistant.play_media` disponible.
2. Copier `custom_components/interphone_live` dans le dossier `custom_components` de Home Assistant, puis redémarrer Home Assistant.
3. Paramètres → Appareils et services → Ajouter une intégration → **Interphone Live**. Compte administrateur requis pour le panneau.
4. Choisir les entités Music Assistant des enceintes. Facultativement, renseigner l’identifiant exact du groupe existant. Le groupe n’est pas créé par cette intégration. Sélectionner ses membres individuels dans la liste des enceintes pour obtenir leurs réglages de volume.
5. Ouvrir **Interphone Live** dans la barre latérale, en HTTPS sur l’iPhone, et autoriser le microphone dans le navigateur. Régler les volumes avant le direct ; ces changements sont immédiats et persistants.
6. Démarrer volontairement un essai à faible volume. Le direct remplace la lecture en cours. Arrêter puis relancer la musique depuis Spotify. Ne pas utiliser simultanément un ancien prototype sur les mêmes enceintes.

Si Music Assistant ne peut pas joindre l’adresse choisie automatiquement, renseigner l’origine locale de Home Assistant accessible depuis son serveur. Le téléphone doit lui aussi pouvoir accéder à Home Assistant : VPN ou accès distant HTTPS déjà sécurisé. L’intégration ne configure ni VPN ni exposition Internet.

Pour les appareils qui coupent le début du message, sélectionner les destinations nécessitant une préparation et ajuster de 0 à 15 secondes (6 par défaut). Inclure explicitement le groupe dans cette sélection si utilisé. Attendre « Parle maintenant ». La préparation transmet du silence et consomme une partie de la limite de 60 secondes.

## Fonctionnement et limites

Audio PCM mono 16 kHz, envoyé par WebSocket authentifié à Home Assistant puis servi en WAV à Music Assistant. Tampon borné (~5 secondes), maximum 60 secondes par transmission, arrêt sur absence de données et sortie de l’écran. Trois lecteurs HTTP maximum. Le serveur ne crée pas de fichier audio. Aucun relais cloud propre au projet.

Le lien WAV est temporaire et accessible sans authentification HA pour permettre sa lecture par Music Assistant ; son jeton aléatoire est un secret donnant accès au flux. Voir SECURITY.md. Les équipements, proxys et journaux externes peuvent conserver des URL ou mettre du son en tampon. Un arrêt du micro n’efface pas l’audio déjà reçu par les enceintes.

La synchronisation et les volumes dépendent de Music Assistant, du groupe configuré et des capacités des appareils. Bluetooth, Cast, AirPlay et Sendspin ne sont pas interchangeables. Aucun retour vocal, réveil « OK Google », appel bidirectionnel ou garantie de livraison. Les changements de nom d’entité nécessitent une reconfiguration dans les options.

## Préparer GitHub et HACS

Dépôt prévu : [koolnino/interphone-live](https://github.com/koolnino/interphone-live). Le dépôt public contient une première version expérimentale. Suivre RELEASE_CHECKLIST.md. Le projet n’a pas été validé par HACS. La structure est prévue pour un dépôt personnalisé HACS ; aucune présence au catalogue officiel n’est promise.

## Vérifications locales

```
python tests/test_audio.py
python tests/test_resume.py
python tests/test_settings.py
python tests/test_bridge.py
python -m compileall -q custom_components
node --check custom_components/interphone_live/panel.js
```

Python 3.13 conseillé ; FFmpeg nécessaire uniquement au test de décodage. Le composant utilise les bibliothèques fournies par Home Assistant. Les tests ne contactent aucune enceinte et ne jouent aucun son.

## Contribuer et alternatives

Voir CONTRIBUTING.md. Pour comparer les usages : [ha-intercom](https://github.com/JoeHogan/ha-intercom), [home-intercom](https://github.com/mdj2812/home-intercom) et les fonctions d’annonces de Music Assistant. Le projet utilise les API de Home Assistant et Music Assistant ; il n’est affilié à aucun de ces projets. Licence MIT.

## Maintien et développement

Mainteneur : [@koolnino](https://github.com/koolnino). Contributions par issues et pull requests. Projet communautaire expérimental, développé avec une assistance IA et soumis à revue humaine ; aucun engagement de délai de correction ou de support commercial. Les marques citées restent celles de leurs titulaires.
