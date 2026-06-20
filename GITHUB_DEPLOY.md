# Publish the repository and project website

The complete repository is already initialized with Git history and includes a GitHub Actions workflow for Pages.

## 1. Create the repository

While logged into GitHub as `mohannad275`, create a new **public** repository named:

`100007801_Aly_AP`

Create it empty. Do not add a README, `.gitignore`, or license on GitHub because they already exist locally.

## 2. Push this folder

Open Terminal in the project folder and run:

```bash
git remote add origin https://github.com/mohannad275/100007801_Aly_AP.git
git branch -M main
git push -u origin main
```

If GitHub asks for authentication, sign in through the browser or use a personal access token.

## 3. Enable GitHub Pages

In the new repository:

1. Open **Settings**.
2. Open **Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Open the **Actions** tab and wait for the `Deploy project website` workflow to finish.

The website will then be available at:

`https://mohannad275.github.io/100007801_Aly_AP/`

The repository will be available at:

`https://github.com/mohannad275/100007801_Aly_AP`

## 4. Final submission

After confirming that the website opens, attach `100007801_Aly_AP.pdf` to the email and use the text in `SUBMISSION_EMAIL.txt`.
