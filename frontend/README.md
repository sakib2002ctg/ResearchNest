# ResearchNest frontend

## Local development

1. Copy `.env.example` to `.env.local`. Set `NEXT_PUBLIC_API_BASE_URL` to the backend origin and `/api/v1` path.
2. Allow that browser origin in backend `CORS_ORIGINS`; the backend defaults include `http://localhost:3000` and `http://127.0.0.1:3000`.
3. Install the locked Node dependencies with `npm ci`.
4. Run `npm run dev`, then open `http://localhost:3000`.

The app uses Next.js App Router, strict TypeScript, Tailwind CSS, and English/Bangla copy. Check with `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build`.

## Authentication model

Bearer access tokens exist only in JavaScript memory and are sent only to the configured API base. They are never written to cookies, local storage, URLs, or browser logs. Refreshing or closing the tab signs the user out; sign in again to create a new revocable server session. API calls omit cookies and reject redirects so credentials cannot be forwarded to another host. The session identifier is displayed only to let the account owner recognize and revoke their own current session; the server performs authorization.

Email verification and password reset tokens are held only in the form component until submission, never in a route or query string. The password-reset endpoint's response stays generic for known and unknown email addresses. Development verification tokens are displayed only when the backend explicitly returns one in an allowed local/test mode. SMTP should be configured before sending real users recovery links.

AI, analysis, writing, projects, insights, citations, and learning routes are labeled preview shells. They do not send content to AI providers or present future features as available.
