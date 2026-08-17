from string import Template

start_response = Template("""
Hi @$username, welcome to LastfmBucket Bot! $setup_lastfm_user

The code of this bot is public: https://github.com/paurieraf/lastfmbucket-bot 

Use /privacy for any privacy-related questions
""")

lastfm_username_set = Template("""
✅ Last.fm username @$lastfm_username set
""")

lastfm_username_set_user_not_found = Template("""
🚫 No Last.fm user has been found with this username: @$lastfm_username
""")

user_not_found = Template("""
🔎 No Last.fm set for your user. Use /set [username] to set your Last.fm username
""")

now_playing = Template("""
@$lastfm_username is currently playing:
🎧 <i>$track_artist</i>  — <strong><a href='$track_url'>$track_title</a></strong>, [$track_album]
""")

now_playing_no_currently_playing = Template("""
<strong>$lastfm_username</strong> is not currently playing music
""")

recent_tracks = Template("""
$telegram_user_first_name is now listening to
$recent_tracks_list
""")

tops_choose_entity_type = Template("""
Choose the type of top you want to see:
""")

tops_choose_period = Template("""
Choose the period for $entity_type:
""")

tops_list = Template("""
Top $entity_type for $period for <a href="https://www.last.fm/user/$lastfm_username">$lastfm_username</a>:

$tops_list
""")

tops_no_available_response = Template("""
There are no tops available for this user: $lastfm_username
""")

collage_choose_entity_type = Template("""
🎨 Choose the entity type for your collage:
""")

collage_choose_size = Template("""
🎨 Choose the grid size for your $entity_type collage:
""")

collage_choose_period = Template("""
🎨 Choose the period for your $size $entity_type collage:
""")

collage_choose_style = Template("""
🎨 Choose the style for your $size $entity_type collage:
$current_style
""")

collage_caption = Template("""
🎨 <b>Top $entity_type collage</b> ($size, $period$tile_note$style_note) for <a href="https://www.last.fm/user/$lastfm_username">$lastfm_username</a>
""")

collage_error = Template("""
🚫 Could not generate collage: $error
""")

privacy = Template("""\
<b>Privacy Policy</b>
This bot is a hobby project and is not a commercial product.

<b>Data Collected</b>
- Your Telegram user ID is stored to associate you with your Last.fm username.
- Your Last.fm username is stored to fetch your music data.
- The bot does not collect any other personal data.

<b>Data Usage</b>
- The collected data is used solely for the purpose of providing the bot's features.
- Your data is not shared with any third parties.

<b>Data Removal</b>
- To remove your data, you can revoke the bot's access from your Telegram settings.
- Alternatively, you can contact the bot developer to have your data manually removed.

<b>License</b>
- This bot is licensed under the GPLv3. The source code is available on <a href="https://github.com/paurieraf/lastfmbucket-bot">GitHub</a>.

For any questions or concerns, please contact the developer.
""")

preferences = Template("""
What do you want to do?
""")

preferences_unlink_account = Template("""
Your account has been unlinked
""")

compare_stats = Template("""
<b>📊 Comparison: $user1 vs $user2</b>

<b>Total Scrobbles</b>
$user1: $playcount1
$user2: $playcount2

<b>🎤 Common Artists ($common_count)</b>
$common_artists

<b>Top Artists</b>
<u>$user1</u>: $top_artists1
<u>$user2</u>: $top_artists2
""")

compare_user_not_found = Template("""
🔎 Last.fm user not found: $username
""")

compare_no_lastfm_set = Template("""
🔎 You need to set your Last.fm username first. Use /set [username]
""")

whoknows_ranking = Template("""\
👑 <b>Who knows <a href="$artist_url">$artist_name</a> in $chat_name?</b>$dethroned_banner

$ranking_list

📊 <b>Group Total:</b> $total_plays scrobbles · $listeners_count listeners
""")

whoknows_no_listeners = Template("""\
👑 Nobody in <b>$chat_name</b> has listened to <b><a href="$artist_url">$artist_name</a></b> yet!
""")

whoknows_artist_not_found = Template("""\
🚫 Could not find artist: <b>$artist_name</b> on Last.fm.
""")

whoknows_no_members = Template("""\
🔎 No linked Last.fm users found in this chat yet. Use /set [username] to link your account!
""")

whoknows_specify_artist = Template("""\
🔎 Please specify an artist name: <code>/whoknows Radiohead</code>, reply to a music message with <code>/wk</code>, or play a track to use your current Now Playing!
""")

crowns_leaderboard = Template("""\
🏆 <b>Crowns Hall of Fame — $chat_name</b>

$leaderboard_list
""")

crowns_no_crowns = Template("""\
🏆 No crowns awarded in <b>$chat_name</b> yet!
Use /whoknows [artist] to discover the group leaders and claim crowns 👑
""")

user_crowns_list = Template("""\
👑 <b>Crowns held by $display_name in $chat_name ($crown_count):</b>

$crowns_list
""")

user_no_crowns = Template("""\
👑 $display_name does not hold any crowns in <b>$chat_name</b> yet.
Keep scrobbling and use /whoknows to claim them!
""")

preferences_opt_out_updated = Template("""\
🔒 Group ranking visibility updated: <b>$status</b>
""")

