# Spec Delta: collage-async-pipeline

## MODIFIED Requirements

### Requirement: Optimized image export formats
El bot SHALL exportar les imatges generades en el format més adient i eficient (amb retorn automàtic a PNG si el format sol·licitat no és suportat) executant la compressió i l'E/S de fitxers temporals fora del bucle d'esdeveniments `asyncio` abans de trametre-les a l'API de Telegram.

#### Scenario: Image compression before upload
- **WHEN** s'ha acabat de compondre una graella visual
- **THEN** s'utilitza l'eina nativa d'exportació de la llibreria (ex: cap a JPEG o WebP) amb qualitat optimitzada executant la compressió i l'E/S del fitxer temporal fora del bucle d'esdeveniments principal
- **AND** s'envia el fitxer resultant a Telegram sense bloquejar altres comandes concurrents

#### Scenario: Unsupported export format falls back cleanly to PNG
- **WHEN** l'exportació amb el format preferit (per exemple WebP) falla per manca de suport
- **THEN** el bot reintenta l'exportació en format PNG fora del bucle d'esdeveniments i retorna el flux PNG vàlid

## ADDED Requirements

### Requirement: Bounded collage disk cache eviction
El bot SHALL aplicar una política d'evicció acotada sobre la memòria cau de disc de collages (`data/collage_cache`) basada en antiguitat màxima (TTL) i mida total màxima configurable, executada fora del bucle d'esdeveniments, de manera que l'ús de disc no pugui créixer indefinidament.

#### Scenario: Expired cache files are evicted by TTL
- **WHEN** la neteja de la memòria cau s'executa i hi ha fitxers més antics que el TTL configurat
- **THEN** aquests fitxers caducats s'eliminen fora del bucle d'esdeveniments

#### Scenario: Oversized cache evicts oldest files until under cap
- **WHEN** la mida total dels fitxers restants a la memòria cau supera el límit màxim configurat
- **THEN** els fitxers més antics s'eliminen en ordre cronològic fins que la mida total quedi dins del límit

#### Scenario: Cache cleanup errors do not fail collage generation
- **WHEN** un fitxer de la memòria cau desapareix o falla en eliminar-se durant la neteja
- **THEN** la neteja ignora l'error de forma segura i la generació de collages continua amb normalitat
