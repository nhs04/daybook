# Daybook

A calm planner for a PhD thesis, PhD applications, courses and emails. It opens on a morning vision board, and has an assistant: you write what you want in your own words, and it files each thing in the right place.

- **Front end:** one page (`index.html`) hosted free on GitHub Pages.
- **Back end:** Supabase (free) stores your data behind a private email sign-in, and runs the AI function.
- **AI:** `supabase/functions/ai` calls Claude (Haiku 5.5) with your Anthropic API key, which stays on the server.

Without any setup, the page still works and saves in your browser only.

---

## Setup (about 20 minutes, once)

### 1. Put the code on GitHub

1. Create a new repository on GitHub, for example `daybook`. It can be public or private (Pages on a private repo needs a paid GitHub plan).
2. Upload everything in this folder to it.

### 2. Create the database

1. Go to [supabase.com](https://supabase.com), sign up, and create a **New project** (the free plan is enough).
2. In the project, open **SQL Editor**, paste the contents of `supabase/migrations/001_daybook.sql`, and click **Run**.

### 3. Connect the page to the database

1. In Supabase, open **Project Settings → API**.
2. Copy the **Project URL** (Project Settings → Data API) and the **anon public** key (Project Settings → API Keys → **Legacy API keys**, it starts with `eyJ`) into `config.js`:

   ```js
   window.DAYBOOK_CONFIG = {
     supabaseUrl: "https://YOUR-PROJECT.supabase.co",
     supabaseAnonKey: "eyJ...",
   };
   ```

3. Commit the change to GitHub. These two values are meant to be public. Your data stays private because of the sign-in and the security rules from step 2.

### 4. Turn on GitHub Pages

1. In your GitHub repository, open **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Open the **Actions** tab, click **Publish Daybook**, then **Run workflow**. After a minute or two your site is live at `https://YOUR-USERNAME.github.io/daybook/`.

From then on, the same workflow runs five times a day (about 5 am, 9 am, 1 pm, 5 pm and 9 pm New York time) and refreshes the **Jobs** tab and **The brief** (AI and cybersecurity news), and it runs again whenever you change a file. An open page picks up the fresh lists on its own every 30 minutes. If GitHub ever pauses it (it does that to repositories with no activity for 60 days; the workflow adds a small commit every ~45 quiet days to prevent it), open the Actions tab and click **Enable workflow**.

### 5. Let sign-in links come back to your site

1. In Supabase, open **Authentication → URL Configuration**.
2. Set **Site URL** to your GitHub Pages address, for example `https://YOUR-USERNAME.github.io/daybook/`.
3. Add the same address under **Redirect URLs**.

### 6. Sign in, then close the door

1. Open your site, type your email, and click the link you receive.
2. Back in Supabase, open **Authentication → Sign In / Providers** and turn off **Allow new users to sign up**. Now only you can use your Daybook.

### 7. Turn on the AI

1. Create an API key at [console.anthropic.com](https://console.anthropic.com) (prepaid credits; the assistant uses Claude Haiku 5.5, so everyday use is usually well under $1 a month, and $5 of credit lasts months).
2. In Supabase, open **Edge Functions → Secrets** and add:
   - `ANTHROPIC_API_KEY`: your key
   - `ALLOWED_EMAIL`: the email you sign in with
3. Deploy the function. Either:
   - **In the dashboard:** Edge Functions → **Deploy a new function** → name it `ai` → paste `supabase/functions/ai/index.ts` → Deploy.
   - **With the command line:**

     ```bash
     npx supabase login
     ```

     ```bash
     npx supabase link --project-ref YOUR-PROJECT-REF
     ```

     ```bash
     npx supabase functions deploy ai
     ```

Reload your site. The input at the top is now the assistant. Until the AI is set up, the same box still works as a quick add.

---

### 8. Bring your Daybook over from Claude

1. In your Daybook inside Claude, scroll to the bottom of the home page and tap **Save a copy of my Daybook**. Save the `my-daybook.json` file.
2. On your website, scroll to the bottom of the home page, tap **Bring my Daybook from Claude**, and choose that file.

Your vision board (with its pictures), applications, courses, thesis and tasks all come across. Keep the file private: it holds your personal data.

---

## Using it

- **Assistant:** write it the way you'd say it, even several things at once: *"Email Prof. Lee friday to ask for a Harvard letter, my Stanford CV is done, and pin 'be brave' to my board."* It adds the email, ticks off the requirement and pins the words, then shows what it did with an **Undo** button.
- **Without the assistant** (before step 7), the same box is a quick add: dates like `friday` or `dec 4`, places like `#thesis`, a university with `@harvard`, or start with `email`.
- **Vision board:** the home page opens on your board. Pin goals, quotes, single words or your own photos, and connect a goal to an application to see its countdown.
- **Jobs:** new grad and early-career tech roles (software, AI/ML/data, product, quant, hardware) in New York City, California and Boston, from the [SimplifyJobs new-grad list](https://github.com/SimplifyJobs/New-Grad-Positions). New York is shown first, with what's new since yesterday at the top. Save a role with ♡, mark it **Applied**, or hide it with ×. The Jobs tab works even before you set up Supabase.
- **Applications:** an empty Applications page offers **Start with my PhD list**, which adds Harvard, MIT, Stanford, Berkeley, Carnegie Mellon and Princeton with their Computer Science PhD deadlines. Always confirm each deadline on the university's own page.

## Files

| File | What it is |
|---|---|
| `index.html` | The whole app: design, pages, saving and sign-in |
| `config.js` | Your Supabase address and public key |
| `scripts/update_jobs.py` | Fetches and filters the daily job list into `jobs.json` |
| `scripts/update_news.py` | Fetches this week's AI and cybersecurity news into `news.json` |
| `.github/workflows/publish.yml` | Publishes the site and refreshes jobs every morning |
| `supabase/migrations/001_daybook.sql` | Creates the private table for your data |
| `supabase/functions/ai/index.ts` | The assistant server (turns your words into actions) |
