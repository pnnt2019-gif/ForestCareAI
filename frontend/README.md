# ForestCare AI Frontend

## Deploy online

This repository includes `../render.yaml` for deploying the frontend and Flask backend together on Render.

1. Push the project to GitHub.
2. In Render, choose **New > Blueprint** and select the repository.
3. Confirm the two services from `render.yaml`.
4. After deployment, set `VITE_API_URL` on the frontend to the public backend URL ending in `/api` if the generated backend URL differs.

For local development, create `.env` from `.env.example`, then run `npm run dev`.

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
