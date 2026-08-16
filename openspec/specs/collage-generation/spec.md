# collage-generation Specification

## Purpose
Permetre als usuaris de Telegram generar i rebre graelles visuals (collages) dels seus elements més escoltats a Last.fm (àlbums, artistes i cançons) en diversos períodes temporals i mides.
## Requirements
### Requirement: Collage generation command
El bot SHALL proporcionar una comanda `/collage` que permeti als usuaris generar collages gràfics dels seus tops musicals de Last.fm.

#### Scenario: Generate default collage with command
- **WHEN** un usuari amb compte de Last.fm vinculat envia `/collage` sense paràmetres
- **THEN** el bot respon amb una graella de collage per defecte (3x3 d'àlbums del període 7 dies) com a foto amb títol/caption informatiu

#### Scenario: Generate custom collage with arguments
- **WHEN** un usuari envia `/collage [mida] [període] [entitat] [mida_casella]` (per exemple `/collage 10x10 overall artist`, `/collage 10x5 1month track 150px` o `/collage 4x4 7day album`)
- **THEN** el bot valida els arguments (dimensions fins a 20x20 i màxim 400 caselles, període, entitat i opcionalment tile_size entre 50 i 600px) i genera la graella corresponent enviant-la com a imatge

#### Scenario: Unlinked user requests collage
- **WHEN** un usuari sense compte de Last.fm registrat al bot envia `/collage`
- **THEN** el bot respon amb un missatge d'error indicant que cal configurar el nom d'usuari de Last.fm amb `/set`

#### Scenario: Invalid parameters provided
- **WHEN** un usuari passa paràmetres invàlids a `/collage` (ex. dimensions superiors a 20x20 o que superin 400 caselles, mida de casella fora de 50-600px, tipus d'entitat desconeguda o període no admès)
- **THEN** el bot respon amb un missatge explicatiu indicant la sintaxi correcta i els valors acceptats

### Requirement: Interactive collage builder interface
El bot SHALL oferir una interfície interactiva mitjançant teclat inline per triar o canviar els paràmetres del collage (entitat, mida i període).

#### Scenario: Interactive selection workflow
- **WHEN** un usuari prem un botó de selecció de collage o sol·licita l'assistent interactiu sense paràmetres
- **THEN** el bot mostra botons per escollir l'entitat (Àlbum, Artista, Cançó), la mida (3x3, 4x4, 5x5, 3x5, 10x5, 10x10) i el període (7 dies, 1 mes, 3 mesos, 6 mesos, 1 any, overall)

#### Scenario: Group chat permission handling
- **WHEN** un usuari prem un botó d'un collage iniciat per un altre usuari en un grup
- **THEN** el bot processa la sol·licitud respectant l'usuari propietari del callback sense barrejar contextos

### Requirement: Non-blocking asynchronous image processing
El bot SHALL generar i processar les imatges de forma no bloquejant per evitar congelar l'atenció de comandes d'altres usuaris.

#### Scenario: Concurrent user interaction during collage generation
- **WHEN** s'està descarregant i generant un collage d'un usuari
- **THEN** el bot continua responent immediatament a comandes d'altres usuaris sense bloquejar l'event loop principal

