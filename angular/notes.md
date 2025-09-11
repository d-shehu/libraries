# Shared Libs Workspace

A workspace for shared libs useful across multiple Angular projects.

1. Create the workspace in the libs directory if it doesn't already exist.

    ```
    ng new libs --no-create-application --directory ./
    ```

2. Create shared library app-shell

    ```
    ng generate library app-shell
    ng build app-shell [--configuration development] [--watch]
    ```

    Optionally build and test if Chrome and tooling installed.

    ```
    ng test app-shell
    ng lint app-shell
    ```

3. Add Material to the library. CD to the workspace.

    ```
    ng add @angular/material --project app-shell
    ```

4. Install the jwt-decode library to enable authentication on client side in the workspace.

    ```
    npm install jwt-decode
    ```

5. Create components and layouts.
    
    ```
    ng generate component components/api-view   --project=app-shell
    ng generate component components/login      --project=app-shell
    ng generate component components/profile    --project=app-shell
    ng generate component components/sign-up    --project=app-shell
    ng generate component components/user-mgmt  --project=app-shell
    ng generate component components/forbidden  --project=app-shell
    ng generate component components/not-found  --project=app-shell
    ```

    ```
    ng generate component layouts/default-layout --project=app-shell
    ```

6. Export components. For each component adding the following line to 'public-api.ts' in 'project/app-shell'.

    ```
    export * from './lib/components/<component>/<component>'
    ```

7. Create services needed by Angular components and downstream apps.

    ```
    ng generate service services/auth/auth --project=app-shell
    ```