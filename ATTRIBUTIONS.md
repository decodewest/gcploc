# Attributions

## Copyright

gcploc is developed and maintained by **Decode West Inc.**

- Website: <https://www.decodewest.com>
- Contact: legal@decodewest.com

---

gcploc is built on the work of many individuals and teams who publish their tools
as open-source software. This file credits those whose packages and container
images are bundled into or distributed alongside gcploc.

---

## Emulator Images

### Google Cloud Pub/Sub Emulator
- **Image:** `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators`
- **Publisher:** Google LLC
- **License:** Apache 2.0
- **Source:** <https://github.com/GoogleCloudPlatform/cloud-sdk-docker>
- **Notes:** Google Cloud CLI Docker image providing the Pub/Sub emulator binary.

### fake-gcs-server
- **Image:** `fsouza/fake-gcs-server`
- **Author:** Francisco Souza
- **License:** BSD 3-Clause
- **Source:** <https://github.com/fsouza/fake-gcs-server>
- **Notes:** A local Cloud Storage emulator with an API-compatible surface for GCS operations.

### Cloud Tasks Emulator
- **Image:** `ghcr.io/aertje/cloud-tasks-emulator`
- **Author:** aertje
- **License:** MIT
- **Source:** <https://github.com/aertje/cloud-tasks-emulator>
- **Notes:** A local emulator for Google Cloud Tasks queue management and scheduling.

### Cloud Firestore Emulator
- **Image:** `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators`
- **Publisher:** Google LLC
- **License:** Apache 2.0
- **Source:** <https://github.com/GoogleCloudPlatform/cloud-sdk-docker>
- **Notes:** Same Cloud SDK image used for Pub/Sub; started with the `firestore` emulator sub-command.

### Cloud Spanner Emulator
- **Image:** `gcr.io/cloud-spanner-emulator/emulator`
- **Publisher:** Google LLC
- **License:** Apache 2.0
- **Source:** <https://github.com/GoogleCloudPlatform/cloud-spanner-emulator>
- **Notes:** Official Cloud Spanner emulator; exposes gRPC on port 9010 and REST on port 9020.

### Cloud Bigtable Emulator
- **Image:** `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators`
- **Publisher:** Google LLC
- **License:** Apache 2.0
- **Source:** <https://github.com/GoogleCloudPlatform/cloud-sdk-docker>
- **Notes:** Same Cloud SDK image used for Pub/Sub; started with the `bigtable` emulator sub-command.

### Secret Manager Fake (Experimental)
- **Image:** `nicholasgasior/gcp-secret-manager-fake` (community image, not official)
- **Author:** nicholasgasior
- **License:** See source repository
- **Source:** <https://github.com/nicholasgasior/gcp-secret-manager-fake>
- **Notes:** Unofficial community image. Not an official Google emulator. Override with `GCPLOC_SECRETMANAGER_IMAGE` if an alternative is preferred.

---

## Python Dependencies

### Click
- **Package:** `click`
- **Author:** Armin Ronacher, Pallets team
- **License:** BSD 3-Clause
- **Source:** <https://github.com/pallets/click>
- **Notes:** Powers the `gcploc` CLI command structure.

---

## Control Panel — Frontend

### React
- **Package:** `react`, `react-dom`
- **Publisher:** Meta Platforms, Inc. and contributors
- **License:** MIT
- **Source:** <https://github.com/facebook/react>

### Vite
- **Package:** `vite`, `@vitejs/plugin-react`
- **Author:** Evan You and Vite contributors
- **License:** MIT
- **Source:** <https://github.com/vitejs/vite>

### TypeScript
- **Package:** `typescript`
- **Publisher:** Microsoft Corporation
- **License:** Apache 2.0
- **Source:** <https://github.com/microsoft/TypeScript>

### Tailwind CSS
- **Package:** `tailwindcss`, `autoprefixer`, `postcss`
- **Publisher:** Tailwind Labs, Inc.
- **License:** MIT
- **Source:** <https://github.com/tailwindlabs/tailwindcss>

### Radix UI
- **Package:** `@radix-ui/react-slot`
- **Publisher:** WorkOS
- **License:** MIT
- **Source:** <https://github.com/radix-ui/primitives>
- **Notes:** Headless, accessible component primitives used as the base for UI components.

### shadcn/ui (component patterns)
- **Author:** shadcn
- **License:** MIT
- **Source:** <https://github.com/shadcn-ui/ui>
- **Notes:** Component design patterns and conventions (Badge, Button, Card) adapted
  in the control panel. Not distributed as a package — source is incorporated directly.

### Lucide React
- **Package:** `lucide-react`
- **Publisher:** Lucide contributors
- **License:** ISC
- **Source:** <https://github.com/lucide-icons/lucide>

### class-variance-authority
- **Package:** `class-variance-authority`
- **Author:** Joe Bell
- **License:** Apache 2.0
- **Source:** <https://github.com/joe-bell/cva>

### clsx
- **Package:** `clsx`
- **Author:** Luke Edwards
- **License:** MIT
- **Source:** <https://github.com/lukeed/clsx>

### tailwind-merge
- **Package:** `tailwind-merge`
- **Author:** Dany Castillo
- **License:** MIT
- **Source:** <https://github.com/nicolo-ribaudo/tailwind-merge>

---

## Toolchain

| Tool | Publisher | License |
|------|-----------|---------|
| Docker Engine | Docker, Inc. | Apache 2.0 |
| Docker Compose | Docker, Inc. | Apache 2.0 |
| Node.js | OpenJS Foundation | MIT |
| Python | Python Software Foundation | PSF-2.0 |

---

*Each package is used in accordance with its respective license. Full license texts
are available in the source repositories listed above.*
