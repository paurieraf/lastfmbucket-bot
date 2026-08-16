# collage-generation Specification

## Requirements

### Requirement: Collage generation command
El bot SHALL proporcionar una comanda `/collage` que permeti als usuaris generar collages gràfics dels seus tops musicals de Last.fm amb suport per a graelles d'1x1 fins a 20x20 (màxim 400 caselles) i resolució dinàmica o personalitzada.

#### Scenario: Generate custom collage with arguments
- **WHEN** un usuari envia `/collage [mida] [període] [entitat] [mida_casella]` (per exemple `/collage 10x10 overall artist`, `/collage 10x5 1month track 150px` o `/collage 4x4 7day album`)
- **THEN** el bot valida els arguments (dimensions fins a 20x20 i màxim 400 caselles, període, entitat i opcionalment tile_size entre 50 i 600px) i genera la graella corresponent enviant-la com a imatge

#### Scenario: Invalid parameters provided
- **WHEN** un usuari passa paràmetres invàlids a `/collage` (ex. dimensions superiors a 20x20 o que superin 400 caselles, mida de casella fora de 50-600px, tipus d'entitat desconeguda o període no admès)
- **THEN** el bot respon amb un missatge explicatiu indicant la sintaxi correcta i els valors acceptats

### Requirement: Interactive collage builder interface
El bot SHALL oferir una interfície interactiva mitjançant teclat inline per triar o canviar els paràmetres del collage (entitat, mida i període) amb presets clàssics i d'alta densitat.

#### Scenario: Interactive selection workflow
- **WHEN** un usuari prem un botó de selecció de collage o sol·licita l'assistent interactiu sense paràmetres
- **THEN** el bot mostra botons per escollir l'entitat (Àlbum, Artista, Cançó), la mida (3x3, 4x4, 5x5, 3x5, 10x5, 10x10) i el període (7 dies, 1 mes, 3 mesos, 6 mesos, 1 any, overall)
