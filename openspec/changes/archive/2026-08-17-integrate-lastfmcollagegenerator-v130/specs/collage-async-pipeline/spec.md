## Purpose
Implementa la generació de collages de forma nativament asíncrona aprofitant la v1.3.0 de la llibreria i el motor d'exportació d'imatges.

## ADDED Requirements

### Requirement: Native asynchronous collage processing
El bot SHALL invocar la versió nativa asíncrona de la generació de collages en lloc d'embolcallar operacions síncrones en subprocessos de Python.

#### Scenario: High concurrency generation
- **WHEN** múltiples usuaris sol·liciten collages simultàniament
- **THEN** el bot aprofita el client HTTP `httpx` asíncron per executar les operacions I/O sense fils secundaris afegits
- **AND** el bucle d'esdeveniments principal respon immediatament

### Requirement: Optimized image export formats
El bot SHALL exportar localment o en memòria les imatges generades amb el format més adient i eficient abans de trametre-les a l'API de Telegram.

#### Scenario: Image compression before upload
- **WHEN** s'ha acabat de compondre una graella visual
- **THEN** s'utilitza l'eina nativa d'exportació de la llibreria (ex: cap a JPEG o WebP) amb qualitat optimitzada
- **AND** s'envia el fitxer resultant per reduir la memòria, el consum d'ample de banda i accelerar la pujada a Telegram
