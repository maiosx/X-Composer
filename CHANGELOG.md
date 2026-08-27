# Changelog

## 1.0.3

- Local state is opened `O_NOFOLLOW|O_NONBLOCK`, then checked as an owned regular file and read with a byte cap. Stdin JSON and X API bodies are similarly bounded.

## 1.0.2

- Hide the overlay as soon as **Continue in X** is pressed.

## 1.0.1

- Enter inserts a newline. Submit only from **Continue in X**.

## 1.0.0

- Fullscreen overlay (`WlrLayer.Overlay`) instead of a bar popover.
- No panel outline or KeyboardPanel chrome — black field, centered serif composer.
- Bar widget is an **X**. Escape dismisses. Continue in X hands off to the browser composer.
- Posting backend adapted from bitr0t.omarchytweet: browser Web Intent by default, paid API opt-in.
