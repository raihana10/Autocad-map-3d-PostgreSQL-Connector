Voici une **définition technique et générale** de TKI PGP que tu peux utiliser dans ton document.

**TKI PGP** signifie **PostgreSQL Provider**. C’est un **logiciel / module de connectivité** développé par l’entreprise **TKI Software / TKI Chemnitz** pour permettre l’utilisation des **Autodesk Industry Models (Fachschalen)** avec une base de données **PostgreSQL**. La documentation officielle le présente comme un **“effective connector”** entre **AutoCAD Map 3D** et PostgreSQL, ce qui montre qu’il ne s’agit pas d’un simple outil autonome, mais d’une **couche d’intégration** entre Autodesk et PostgreSQL. [help.tki-chemnitz](https://help.tki-chemnitz.de/hc/en-gb/articles/360015894560-Introduction-PostgreSQL-provider)

## Nature technique
PGP est donc :
- un **provider** au sens fonctionnel, c’est-à-dire un composant qui permet à une application cliente de travailler avec PostgreSQL via une logique adaptée aux modèles Autodesk. [help.tki-chemnitz](https://help.tki-chemnitz.de/hc/en-gb/articles/360015894560-Introduction-PostgreSQL-provider)
- un **connecteur applicatif** pour les fachschalen Autodesk, avec des fonctions d’administration et d’échange de données. [tki-chemnitz](https://www.tki-chemnitz.com/software/products/pgp.html)
- un produit commercial qui nécessite une **licence** et une compatibilité de version avec AutoCAD Map 3D. [help.tki-chemnitz](https://help.tki-chemnitz.de/hc/en-gb/sections/360004497540-PostgreSQL-Provider-PGP)

## Entreprise éditrice
Le produit est porté par **TKI**, présenté dans la documentation comme **TKI Software** et **TKI Chemnitz** selon les sites et portails d’aide officiels. [tki-net](https://www.tki-net.com/products/pgp.html)
Le portail d’aide TKI est structuré autour d’une section dédiée à **PostgreSQL Provider (PGP)**, ce qui confirme qu’il s’agit d’un produit officiel de la société, et non d’un plugin communautaire. [help.tki-chemnitz](https://help.tki-chemnitz.de/hc/en-gb/sections/360004497540-PostgreSQL-Provider-PGP)

## Fonction générale
Sa fonction principale est de permettre à des **Fachschalen Autodesk** d’être exploitées avec **PostgreSQL** au lieu d’autres SGBD plus traditionnels dans l’écosystème Autodesk. [tki-chemnitz](https://www.tki-chemnitz.de/de/software/produkte/pgp.html)
La documentation indique aussi qu’il prend en charge :
- les fonctionnalités de l’**Infrastructure Administrator**,
- l’**import/export de dumps PostgreSQL**,
- le **SQL sheet** de Map 3D. [tki-chemnitz](https://www.tki-chemnitz.com/software/products/pgp.html)

## Date et origine
Dans les sources publiques consultées ici, je n’ai pas trouvé une **année de création/invention explicitement indiquée** pour le produit. [help.tki-chemnitz](https://help.tki-chemnitz.de/hc/en-gb/articles/360015894560-Introduction-PostgreSQL-provider)
En revanche, la documentation montre que le produit existe au moins depuis qu’il apparaît dans le centre d’aide TKI et dans les pages produits officielles, avec des mises à jour récentes visibles sur les pages TKI. [tki-chemnitz](https://www.tki-chemnitz.de/de/software/produkte/pgp.html)

## Formulation prête à mettre dans ton rapport
Tu peux écrire :

> TKI PGP (PostgreSQL Provider) est un logiciel de connectivité édité par TKI Software / TKI Chemnitz. Il sert de connecteur fonctionnel entre Autodesk AutoCAD Map 3D, ses Industry Models (Fachschalen) et une base de données PostgreSQL. Il s’agit donc d’une couche d’intégration applicative et non d’un simple driver de base de données. La documentation officielle lui attribue également des fonctions d’administration, d’import/export de dumps PostgreSQL et de support du SQL sheet de Map 3D. [help.tki-chemnitz](https://help.tki-chemnitz.de/hc/en-gb/sections/360004497540-PostgreSQL-Provider-PGP)

Si tu veux, je peux maintenant te rédiger la **version académique complète de la présentation générale** en 1 page, prête à coller dans ton fichier `04-role-tki-pgp.md`.