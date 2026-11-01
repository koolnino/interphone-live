# Validation locale de la bêta

Vérifications effectuées le 1 novembre 2026, sans appel réseau à Home Assistant ni lecture réelle :

- Tests du tampon audio, limites, fermeture et décodage WAV par FFmpeg : réussis.
- Scénarios simulés de reprise Spotify : réussis ; pas de validation réelle de cette fonction.
- Validation des paramètres, restrictions de destinations, propriété des sessions, jetons mal formés et état désactivé : réussies en isolation.
- Compilation Python, syntaxe JavaScript et lecture de tous les JSON : réussies.
- Revue des fichiers livrés et recherche de motifs privés connus, adresses domestiques et adresses MAC : aucune correspondance détectée.

La compilation ne valide pas les API Home Assistant. Installation réelle, config/options flow, cycle de rechargement, microphone iOS, HACS/hassfest et restitution sur appareils restent à vérifier. Voir RELEASE_CHECKLIST.md.
