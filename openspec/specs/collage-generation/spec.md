# collage-generation Specification

## Purpose
Permetre als usuaris de Telegram generar i rebre graelles visuals (collages) dels seus elements més escoltats a Last.fm (àlbums, artistes i cançons) en diversos períodes temporals i mides.

## Requirements

### Requirement: Collage generation command
The bot SHALL provide a `/collage` command supporting grid dimensions, periods, entities, tile sizes, themes, overlays, social presets, filters, and geometry options, escaping all error messages and caption metadata for HTML and rendering caption style notes in English (`no text`, `filter <name>`).

#### Scenario: Generate default collage with command
- **WHEN** a user with a linked Last.fm account sends `/collage` without parameters
- **THEN** the bot responds with the interactive selection or default 3x3 album collage for the 7-day period as a photo with an informative HTML-escaped caption

#### Scenario: Generate custom collage with arguments
- **WHEN** a user sends `/collage [size] [period] [entity] [tile_size]` (e.g. `/collage 10x10 overall artist`, `/collage 10x5 1month track 150px`, or `/collage 4x4 7day album`)
- **THEN** the bot validates the arguments (up to 20x20 and 400 tiles max, period, entity, and optional tile_size 50–600px) and sends the generated grid image

#### Scenario: Generate collage with rendering options
- **WHEN** a user sends `/collage` with valid rendering options (`theme:<dark|light|glassmorphic|sunset|neon|adaptive>`, `overlay:<banner|full_tint|gradient|pill|clean>`, `notext`, `bold`, `filter:<name>`, `corner:<n>`, `border:<n>`, `border_color:<hex>`, `spacing:<n>`, `fallback:<gradient|black>`)
- **THEN** the bot generates the collage with those options via the async pipeline and reflects non-default options in English in the caption

#### Scenario: Generate collage with social preset
- **WHEN** a user sends `/collage` with `preset:<name>` (or short aliases `story`, `post`, `header`, `wallpaper`, `4k`)
- **THEN** the bot generates the collage using the preset dimensions (overriding size/tile_size) and displays the preset in the caption

#### Scenario: Unlinked user requests collage
- **WHEN** a user without a linked Last.fm account sends `/collage`
- **THEN** the bot replies with an error indicating they need to link their Last.fm username with `/set`

#### Scenario: Invalid parameters provided
- **WHEN** a user passes invalid parameters to `/collage` (such as dimensions > 20x20 or > 400 tiles, tile_size outside 50–600px, unknown entity/period/theme/overlay/filter/preset/fallback, or negative geometry values)
- **THEN** the bot replies with an HTML-escaped explanatory error message showing valid syntax and options

#### Scenario: Invalid collage parameter containing HTML characters
- **WHEN** a user runs `/collage <script>` or passes an invalid option containing `<`, `>`, or `&`
- **THEN** the error message is HTML-escaped and delivered cleanly without Telegram `BadRequest`

#### Scenario: Collage caption with style options
- **WHEN** a user generates a collage with `notext` and `filter:duotone`
- **THEN** the caption displays English style labels (`no text`, `filter duotone`) and HTML-escapes the Last.fm username and filter name

### Requirement: Interactive collage builder interface
The bot SHALL offer an inline-keyboard collage wizard with owner-enforced callbacks encoded under 64 bytes, a clear generation button (`✨ Skip & Generate` before style selection or `✅ Generate` after selecting a style), and automatic cleanup of the temporary `"Generating..."` status message in a `finally` block.

#### Scenario: Interactive selection workflow
- **WHEN** a user presses a collage selection button or starts `/collage` without arguments
- **THEN** the bot displays inline buttons to choose entity (Artist, Album, Track), size (3x3, 4x4, 5x5, 3x5, 10x5, 10x10) or social preset (Story, Post, Header, Wallpaper, 4K), period (1week, 1month, 3month, 6month, 1year, alltime), and style/effects

#### Scenario: Style step can be skipped
- **WHEN** the owning user reaches the style step without picking a custom theme/overlay and clicks `✨ Skip & Generate` (or clicks `✅ Generate` after picking a style)
- **THEN** the bot generates and sends the collage photo with the selected or default style and deletes the temporary `"Generating..."` status message in `finally` regardless of success or error

#### Scenario: Group chat permission handling
- **WHEN** another group member taps a button on a collage wizard started by `owner_id`
- **THEN** the bot answers the callback with `show_alert=True` ("This button belongs to another user.") and leaves the wizard message untouched

### Requirement: Non-blocking asynchronous image processing
El bot SHALL generar, processar i exportar les imatges de forma nativament asíncrona i no bloquejant per evitar congelar l'atenció de comandes d'altres usuaris.

#### Scenario: Concurrent user interaction during collage generation
- **WHEN** s'està descarregant i generant un collage d'un usuari utilitzant `generate_async`
- **THEN** l'ús de threads és innecessari i el bucle d'esdeveniments de `python-telegram-bot` continua responent immediatament a comandes d'altres usuaris
