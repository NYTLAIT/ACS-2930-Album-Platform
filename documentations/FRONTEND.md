# AlbumRank — Frontend Documentation

How the templates, CSS, and JavaScript work together.

---

## Table of Contents

1. [Overview](#1-overview)
2. [How Templates Work](#2-how-templates-work)
3. [Template by Template](#3-template-by-template)
4. [The scroll_card Macro](#4-the-scroll_card-macro)
5. [How AJAX Works](#5-how-ajax-works)
6. [AJAX Actions by Page](#6-ajax-actions-by-page)
7. [CSS Architecture](#7-css-architecture)
8. [Design Tokens](#8-design-tokens)
9. [Flash Messages](#9-flash-messages)
10. [Common Gotchas](#10-common-gotchas)

---

## 1. Overview

The frontend is built with:
- **Jinja2** — Python's templating engine, baked into Flask. Renders HTML server-side.
- **Vanilla JavaScript (ES6)** — handles all interactive actions (ratings, moods, notes, votes, modals) without a framework
- **CSS custom properties** — a design system defined in `global.css` and imported by every page

There is no build step, no bundler, and no frontend framework. Everything is plain HTML, CSS, and JavaScript served directly by Flask.

---

## 2. How Templates Work

Templates live in the `templates/` folder. Flask renders them with `render_template('filename.html', variable=value, ...)`. Variables passed from the route become available in the template.

### Jinja2 Basics

```jinja
{# This is a comment #}

{# Display a variable #}
<h1>{{ album.name }}</h1>

{# Loop #}
{% for album in albums %}
  <p>{{ album.artist }}</p>
{% endfor %}

{# Conditional #}
{% if user_rating == 1 %}
  <span>You liked this</span>
{% elif user_rating == -1 %}
  <span>You disliked this</span>
{% else %}
  <span>Not rated</span>
{% endif %}

{# Generate a URL — always use url_for, never hardcode paths #}
<a href="{{ url_for('album_detail', album_id=album.id) }}">{{ album.name }}</a>
```

### Passing Data to JavaScript

Never put Python values directly into JavaScript strings — quotes and special characters will break it. Instead, use `data-` attributes on HTML elements and read them in JavaScript:

```html
<!-- In the template -->
<button class="btn-like"
        data-album-id="{{ album.id }}"
        data-current-rating="{{ user_rating or 0 }}">
  Like
</button>
```

```javascript
// In the JavaScript
btn.addEventListener('click', () => {
  const albumId = btn.dataset.albumId;
  const rating  = btn.dataset.currentRating;
});
```

---

## 3. Template by Template

### `landing.html`
Public page — no login required. Hero section with tagline, feature highlights, and call-to-action buttons linking to `/signup` and `/login`.

### `login.html` and `signup.html`
Auth forms using Flask-WTF. Both must include `{{ form.hidden_tag() }}` for the CSRF token — without it, every form submission is silently rejected and the page just refreshes. Validation errors are shown field-by-field using `{% if form.field.errors %}`.

### `dashboard.html`
The main page after login. Contains:
- **Welcome section** with inline search bar
- **Mood filter bar** — 15 clickable tag links that toggle mood filters. Clicking a tag adds or removes it from the `?moods=` query parameter. The "Match any / Match all" toggle changes `?mood_mode=`.
- **6 discovery sections** — Recent Activity, Trending, Top Rated, New Arrivals, You Might Like, Your Collections
- **The `scroll_card` macro** — defined here and used by all 5 album discovery sections

**Important:** The macro must be defined in the template *before* it is first called. If you move the macro definition below the first `{{ scroll_card(...) }}` call, Jinja2 throws `UndefinedError: 'scroll_card' is undefined`.

### `search_results.html`
Displays Spotify search results in a grid. Each card has an "Add to Collection" button that opens a modal. The modal lists the user's collections and has a "Create new collection" inline form. All of this runs via AJAX — no page reload.

### `collections.html`
Shows all of the user's collections as cards. Each card shows a cover strip (up to 4 album thumbnails). Has Edit and Delete modals that appear as overlays.

### `create_collection.html`
Simple form with name, description, and a public/private toggle.

### `view_collection.html`
Shows all albums in a single collection as a grid. Each card has Like/Dislike buttons that call `/rate_album` via AJAX. Album covers and names both link to `/album/<id>`.

### `album_detail.html`
Two-column layout:
- **Left (main)**: album header (cover, title, artist, meta), tracklist, comments section
- **Right (sidebar)**: Like/Dislike buttons with community counts, private notes textarea, mood tag picker

All sidebar interactions (rating, notes, mood tags) and comment voting are AJAX — they update in place without a page reload. Posting a new comment or reply is a regular form POST (page reloads, anchored to `#comments`).

### `artist.html`
Artist hero section with a blurred background image, follower count, genre tags, and a discography grid. All data is fetched live from Spotify on every page load. Albums that exist in the local database show a link to their detail page.

---

## 4. The scroll_card Macro

The `scroll_card` macro is defined in `dashboard.html` and renders a consistent album card used across all 5 discovery sections.

```jinja
{% macro scroll_card(album, user_rating, like_count=None) %}
<div class="scroll-card" id="card-{{ album.id }}">
  <a href="{{ url_for('album_detail', album_id=album.id) }}" class="scroll-card-img-link">
    <img src="{{ album.image_url }}" class="scroll-card-img">
    {% if like_count %}
      <span class="like-badge">{{ like_count }} liked</span>
    {% endif %}
  </a>
  <div class="scroll-card-info">
    <a href="{{ url_for('album_detail', album_id=album.id) }}">{{ album.name }}</a>
    ...Like/Dislike buttons...
  </div>
</div>
{% endmacro %}
```

Called like this:

```jinja
{{ scroll_card(album, ratings.get(album.id)) }}
{{ scroll_card(item.album, ratings.get(item.album.id), item.like_count) }}
```

The `like_count` parameter is optional — it shows a badge on cards in sections like Trending and Top Rated where the count is meaningful.

---

## 5. How AJAX Works

AJAX lets JavaScript send data to the server and update the page without reloading. AlbumRank uses the browser's built-in `fetch()` API everywhere.

### The Pattern

Every AJAX call follows the same structure:

```javascript
// 1. Build the form data
const body = new FormData();
body.append('album_id', albumId);
body.append('rating', '1');

// 2. Send it
fetch('/rate_album', { method: 'POST', body })
  .then(res => res.json())
  .then(data => {
    // 3. Update the page based on the response
    if (data.status === 'added') {
      btn.classList.add('active');
    }
  });
```

The server always returns JSON. The JavaScript reads the response and updates only the relevant part of the page (a button class, a score number, a toast message).

### Toast Notifications

Several pages show a temporary "toast" notification after an AJAX action succeeds. This is implemented in JavaScript by creating a `<div class="toast">` element, appending it to the body, and removing it after a short delay.

---

## 6. AJAX Actions by Page

### dashboard.html — Like/Dislike

```javascript
document.addEventListener('click', function(e) {
  const btn = e.target.closest('[data-action="rate"]');
  if (!btn) return;

  const body = new FormData();
  body.append('album_id', btn.dataset.albumId);
  body.append('rating', btn.dataset.rating);

  fetch('/rate_album', { method: 'POST', body })
    .then(r => r.json())
    .then(data => {
      // update like/dislike button active states
    });
});
```

Uses event delegation — one listener on `document` catches all rating buttons, identified by `data-action="rate"`.

### search_results.html — Add to Collection Modal

```javascript
// Open modal
document.querySelectorAll('.btn-add-collection').forEach(btn => {
  btn.addEventListener('click', () => {
    // store album data from data- attributes
    // show the modal
  });
});

// Pick a collection
document.querySelectorAll('.collection-item').forEach(item => {
  item.addEventListener('click', () => {
    const body = new FormData();
    body.append('spotify_id', currentAlbum.spotifyId);
    body.append('collection_id', item.dataset.collectionId);
    // ... other album fields

    fetch('/add_to_collection', { method: 'POST', body })
      .then(r => r.json())
      .then(data => { /* show confirmation */ });
  });
});

// Create new collection inline
fetch('/create_collection', {
  method: 'POST',
  headers: { 'X-Requested-With': 'XMLHttpRequest' },
  body
}).then(r => r.json())
  .then(data => {
    // append new collection to the modal list
  });
```

The `X-Requested-With: XMLHttpRequest` header tells the route to return JSON instead of redirecting.

### album_detail.html — Rating

```javascript
document.querySelectorAll('.btn-rate').forEach(btn => {
  btn.addEventListener('click', () => {
    const body = new FormData();
    body.append('album_id', btn.dataset.albumId);
    body.append('rating', btn.dataset.value);

    fetch('/rate_album', { method: 'POST', body })
      .then(r => r.json())
      .then(data => {
        // update both Like and Dislike button states
        // update the community count displays
      });
  });
});
```

### album_detail.html — Mood Tags

```javascript
document.querySelectorAll('.btn-mood').forEach(btn => {
  btn.addEventListener('click', () => {
    const body = new FormData();
    body.append('album_id', ALBUM_ID);
    body.append('mood_tag_id', btn.dataset.tagId);

    fetch('/tag_mood', { method: 'POST', body })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'limit_reached') {
          // show warning
        } else {
          btn.classList.toggle('mood-active');
        }
      });
  });
});
```

### album_detail.html — Private Notes

```javascript
document.getElementById('notesForm').addEventListener('submit', e => {
  e.preventDefault();  // stop the page from reloading

  const body = new FormData();
  body.append('album_id', ALBUM_ID);
  body.append('notes', textarea.value);

  fetch('/save_note', { method: 'POST', body })
    .then(r => r.json())
    .then(() => { /* show saved confirmation */ });
});
```

### album_detail.html — Comment Voting

```javascript
document.querySelectorAll('.btn-vote').forEach(btn => {
  btn.addEventListener('click', () => {
    const body = new FormData();
    body.append('comment_id', btn.dataset.commentId);
    body.append('value', btn.dataset.value);

    fetch('/vote_comment', { method: 'POST', body })
      .then(r => r.json())
      .then(data => {
        // update the score display for this comment
      });
  });
});
```

### album_detail.html — Reply Forms

Toggling reply forms is pure DOM manipulation — no server call needed:

```javascript
document.querySelectorAll('.btn-reply').forEach(btn => {
  btn.addEventListener('click', () => {
    const form = document.getElementById(`reply-form-${btn.dataset.commentId}`);
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
  });
});
```

---

## 7. CSS Architecture

Each page has its own CSS file. Every file starts by importing `global.css`:

```css
/* Inside home.css, album_detail.css, etc. */
/* global.css is loaded via a separate <link> tag in the HTML head */
```

Actually in AlbumRank, each template loads `global.css` and its own CSS file as separate `<link>` tags:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='global.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='dashboard.css') }}">
```

### File Responsibilities

| File | What it styles |
|------|----------------|
| `global.css` | CSS variables, reset, navbar, album cards, buttons, modals, toast, flash messages |
| `dashboard.css` | Discovery sections, scroll rows, mood filter bar, collection chips |
| `auth.css` | Login and signup cards, form inputs, validation errors |
| `landing.css` | Hero section, features grid, CTA |
| `collections.css` | Collection card grid, cover strip thumbnails |
| `album_detail.css` | Two-column layout, tracklist, comment threads, sidebar cards, mood picker |
| `artist.css` | Artist hero with blur background, discography grid |
| `search.css` | Search results grid, Add to Collection modal |

---

## 8. Design Tokens

All colours, fonts, spacing, and effects are defined as CSS custom properties in `global.css`. Use these instead of hardcoding values anywhere.

```css
:root {
  /* Colours */
  --bg:          #121212;   /* page background */
  --surface:     #1e1e1e;   /* cards, panels */
  --surface-2:   #2a2a2a;   /* elevated surfaces */
  --border:      #2e2e2e;   /* borders */
  --accent:      #ff5f6d;   /* primary accent (coral/red) */
  --accent-warm: #ffc371;   /* secondary accent (gold) */
  --text:        #f0f0f0;   /* primary text */
  --muted:       #888888;   /* secondary text */
  --like:        #4ade80;   /* green for likes */
  --dislike:     #f87171;   /* red for dislikes */

  /* Border radius */
  --r-sm:   6px;
  --r-md:   12px;
  --r-lg:   20px;
  --r-pill: 50px;

  /* Typography */
  --font-body:    "Roboto", sans-serif;
  --font-display: "Montserrat", sans-serif;

  /* Transitions */
  --ease: 0.2s ease;

  /* Shadows */
  --shadow-card:  0 4px 16px rgba(0,0,0,0.3);
  --shadow-modal: 0 16px 48px rgba(0,0,0,0.5);
}
```

**To change the accent colour across the whole app**, edit `--accent` in `global.css`. Every button, link, and highlighted element updates automatically.

---

## 9. Flash Messages

Flask's `flash()` queues a one-time notification. Templates display them like this:

```jinja
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <div class="flash-container">
      {% for category, message in messages %}
        <div class="flash-message {{ category }}">{{ message }}</div>
      {% endfor %}
    </div>
  {% endif %}
{% endwith %}
```

Categories used in AlbumRank: `success`, `danger`, `info`. These map to CSS classes in `global.css` that apply different background colours.

---

## 10. Common Gotchas

### CSRF Token Missing
Every Flask-WTF form must include `{{ form.hidden_tag() }}`. Without it, all POST submissions silently fail and the form just re-renders. No error is shown. This is the most common cause of "the form doesn't do anything".

### Jinja2 Macro Ordering
Macros must be defined in the template *before* they are called. If `scroll_card` is defined at line 257 but called at line 104, you get `UndefinedError: 'scroll_card' is undefined`. Move the macro definition to the top of the template body.

### Album Links Not Working
Album name and cover image should both be wrapped in `<a href="{{ url_for('album_detail', album_id=album.id) }}">`. If only the text is a link and the image is not, clicking the image does nothing.

### AJAX and CSRF
Flask-WTF's CSRF protection applies to form submissions. AJAX calls using `FormData` and `fetch()` bypass Flask-WTF because they don't go through a `FlaskForm` object — they read `request.form.get()` directly. This means AJAX routes don't need `form.hidden_tag()` but they also get no automatic CSRF protection.

### data- Attributes for Dynamic Values
Never inject Python values directly into JavaScript strings in template attributes. Use `data-` attributes on elements and read them with `element.dataset.propertyName` in JavaScript. This avoids quote-breaking bugs with apostrophes or special characters in album/artist names.

### `url_for()` Everywhere
Never hardcode URLs like `/dashboard` or `/album/1` in templates. Always use `url_for('function_name', param=value)`. This ensures links stay correct if routes are ever renamed or moved.