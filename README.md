# X Composer

![X Composer preview](preview.png)

A fullscreen Omarchy overlay for composing X posts. Black field, no outline, centered serif composer. Click the **X** in the bar. Escape dismisses.

Built from the same overlay template as Soprano and Runway: `WlrLayer.Overlay`, exclusive keyboard focus, `keepLoaded`, bar-widget toggle.

Posting is a browser handoff by default (`https://x.com/intent/tweet`). Paid X API posting is an explicit opt-in.

## Install

```bash
omarchy plugin add https://github.com/maiosx/X-Composer.git --enable --yes
```

For a local checkout:

```bash
plugin_dir="$HOME/.config/omarchy/plugins/x.composer"
mkdir -p "$(dirname "$plugin_dir")"
ln -s "$PWD" "$plugin_dir"
omarchy-shell shell rescanPlugins
omarchy plugin enable x.composer
```

Enable the **X Composer** bar widget from Setup → Bar if it does not appear on the right side.

## Use

- Click **X** in the bar to open or close the overlay.
- Type in the centered serif field. There is no panel chrome and no outline.
- **Continue in X** hands off to the web composer (or posts, in paid API mode). **Escape** dismisses.
- Drafts persist across open/close cycles.

IPC:

```bash
omarchy-shell shell toggle x.composer
omarchy-shell xcomposer toggle|open|close|status
omarchy-shell xcomposer compose "hello from IPC"
```

## Configure

```bash
mkdir -m 700 -p ~/.config/xtweet
cp ~/.config/omarchy/plugins/x.composer/config.example.toml ~/.config/xtweet/config.toml
chmod 600 ~/.config/xtweet/config.toml
```

Leave `paid_api = false` (the default) to hand off to the X web composer. Set `paid_api = true` and fill all four OAuth 1.0a fields to post directly via `POST /2/tweets`. Partial credentials stay on the free Web Intent.

Pricing is pay-per-use and changes; the [X Developer Console](https://developer.x.com) is authoritative.

## Optional CLI

```bash
ln -sf ~/.config/omarchy/plugins/x.composer/bin/xtweet ~/.local/bin/xtweet
printf '%s' 'Your post text here' | xtweet post
```

Post text is always passed on **stdin**, never as a command-line argument.

## Remove

```bash
omarchy plugin disable x.composer
omarchy plugin remove x.composer --yes
rm -f ~/.local/bin/xtweet
rm -rf ~/.config/xtweet
```

## License

MIT — see [LICENSE](LICENSE). Posting backend adapted from [bitr0t.omarchytweet](https://github.com/rmacy/omarchytweet) (Ryan Macy, MIT).
