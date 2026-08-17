# collage-advanced-visuals Specification

## Purpose
Exposa les capacitats visuals avançades de lastfmcollagegenerator (filtres i tipografia bold) a la comanda de Telegram.
## Requirements
### Requirement: Advanced rendering options in command
El bot SHALL acceptar paràmetres addicionals per aplicar filtres visuals i estils tipogràfics a la comanda `/collage`.

#### Scenario: Generate collage with image filters
- **WHEN** un usuari afegeix el paràmetre `filter:<nom_filtre>` (ex. `filter:duotone`) a la comanda `/collage`
- **THEN** el bot aplica el pipeline d'efectes visuals de la llibreria i genera el collage amb aquest filtre
- **AND** ho reflecteix al caption si és diferent del per defecte

#### Scenario: Generate collage with bold text
- **WHEN** un usuari afegeix el paràmetre `bold` a la comanda `/collage`
- **THEN** el bot crida el generador activant la tipografia en negreta per al text de les caselles

