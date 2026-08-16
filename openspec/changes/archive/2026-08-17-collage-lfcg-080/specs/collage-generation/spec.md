## MODIFIED Requirements

### Requirement: Collage generation command
El bot SHALL proporcionar una comanda `/collage` que permeti als usuaris generar collages gràfics dels seus tops musicals de Last.fm, amb opcions de renderitzat (tema, overlay, preset, geometria de caselles, amagat de text i estil de fallback).

#### Scenario: Generate default collage with command
- **WHEN** un usuari amb compte de Last.fm vinculat envia `/collage` sense paràmetres
- **THEN** el bot respon amb una graella de collage per defecte (3x3 d'àlbums del període 7 dies) com a foto amb títol/caption informatiu

#### Scenario: Generate custom collage with arguments
- **WHEN** un usuari envia `/collage [mida] [període] [entitat] [mida_casella]` (per exemple `/collage 10x10 overall artist`, `/collage 10x5 1month track 150px` o `/collage 4x4 7day album`)
- **THEN** el bot valida els arguments (dimensions fins a 20x20 i màxim 400 caselles, període, entitat i opcionalment tile_size entre 50 i 600px) i genera la graella corresponent enviant-la com a imatge

#### Scenario: Generate collage with rendering options
- **WHEN** un usuari envia `/collage` amb opcions de renderitzat vàlides (`theme:<dark|light|glassmorphic|sunset|neon>`, `overlay:<banner|full_tint|gradient|pill|clean>`, `notext`, `corner:<n>`, `border:<n>`, `border_color:<hex>`, `spacing:<n>`, `fallback:<gradient|black>`), soles o combinades amb mida/període/entitat
- **THEN** el bot genera el collage amb el renderitzat demanat i ho reflecteix al caption quan els valors difereixen dels per defecte

#### Scenario: Generate collage with social preset
- **WHEN** un usuari envia `/collage` amb `preset:<nom>` (o els àlies curts `story`, `post`, `header`, `wallpaper`, `4k`) amb un dels presets suportats (`instagram-story`, `instagram-post`, `twitter-header`, `desktop-wallpaper`, `desktop-wallpaper-4k`)
- **THEN** el bot genera el collage amb les dimensions del preset, que sobreescriuen qualsevol mida o tile_size indicats, i el caption mostra el preset utilitzat

#### Scenario: Unlinked user requests collage
- **WHEN** un usuari sense compte de Last.fm registrat al bot envia `/collage`
- **THEN** el bot respon amb un missatge d'error indicant que cal configurar el nom d'usuari de Last.fm amb `/set`

#### Scenario: Invalid parameters provided
- **WHEN** un usuari passa paràmetres invàlids a `/collage` (ex. dimensions superiors a 20x20 o que superin 400 caselles, mida de casella fora de 50-600px, tipus d'entitat desconeguda, període no admès, tema, overlay, preset o estil de fallback desconeguts, o valors de geometria negatius)
- **THEN** el bot respon amb un missatge explicatiu indicant la sintaxi correcta i els valors acceptats

### Requirement: Interactive collage builder interface
El bot SHALL oferir una interfície interactiva mitjançant teclat inline per triar o canviar els paràmetres del collage (entitat, mida o preset social, període i estil de renderitzat).

#### Scenario: Interactive selection workflow
- **WHEN** un usuari prem un botó de selecció de collage o sol·licita l'assistent interactiu sense paràmetres
- **THEN** el bot mostra botons per escollir l'entitat (Àlbum, Artista, Cançó), la mida (3x3, 4x4, 5x5, 3x5, 10x5, 10x10) o un preset social (Story, Post, Header, Wallpaper, 4K), el període (7 dies, 1 mes, 3 mesos, 6 mesos, 1 any, overall) i l'estil (temes Dark, Light, Glassmorphic, Sunset, Neon; overlays Banner, Full tint, Gradient, Pill, Clean)

#### Scenario: Style step can be skipped
- **WHEN** un usuari arriba al pas d'estil de l'assistent interactiu i prem el botó "Skip"
- **THEN** el bot genera el collage amb l'estil per defecte (tema dark, overlay banner, text visible)

#### Scenario: Group chat permission handling
- **WHEN** un usuari prem un botó d'un collage iniciat per un altre usuari en un grup
- **THEN** el bot processa la sol·licitud respectant l'usuari propietari del callback sense barrejar contextos

### Requirement: Non-blocking asynchronous image processing
El bot SHALL generar i processar les imatges de forma no bloquejant per evitar congelar l'atenció de comandes d'altres usuaris.

#### Scenario: Concurrent user interaction during collage generation
- **WHEN** s'està descarregant i generant un collage d'un usuari
- **THEN** el bot continua responent immediatament a comandes d'altres usuaris sense bloquejar l'event loop principal
