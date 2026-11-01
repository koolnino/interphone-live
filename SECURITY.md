# Sécurité et confidentialité

Bêta non auditée indépendamment. Panneau et commandes WebSocket réservés aux administrateurs HA. Le flux WAV utilise une URL porteuse d’un jeton aléatoire de 256 bits, temporaire, avec durée maximale de 65 secondes depuis le début de session. Ne partagez jamais ce lien. La session est liée à la connexion WebSocket qui l’a créée.

Pas d’enregistrement audio sur disque dans ce composant. Le serveur, le téléphone, Music Assistant et les enceintes traitent le son en mémoire ; les proxys et autres logiciels ont leurs propres politiques. Exclure les chemins `/api/interphone_live/audio/` des journaux d’accès, utiliser HTTPS sur les réseaux non fiables et protéger l’accès distant à HA. Ne pas ouvrir de port audio supplémentaire.

Avant un signalement public, retirer URL, jetons, adresses IP/MAC, noms de personnes, identifiants d’appareils et captures privées. Pour une faille, utiliser le signalement privé GitHub à https://github.com/koolnino/interphone-live/security/advisories/new une fois activé. Si ce canal est indisponible, ne pas publier de détails exploitables dans une issue publique ; demander uniquement un moyen de contact privé au mainteneur @koolnino.
