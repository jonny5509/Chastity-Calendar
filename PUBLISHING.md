# Publishing Chastity Calendar

This repository is structured as a Home Assistant custom integration for HACS.

## Before publishing a release

1. Ensure the validation workflows pass on the branch or pull request.
2. Test installation and setup against a real Home Assistant instance, including each optional service and the Obedience authorization callback.
3. Update `custom_components/chastity_calendar/manifest.json` version when preparing a release.
4. Update the README if setup steps, configuration options, or supported Home Assistant versions changed.
5. Merge the reviewed changes to the default branch.
6. Create a GitHub release and tag the release with the same version as the integration manifest (for example, `v1.0.1` for manifest version `1.0.1`).
7. Verify the release can be installed through HACS and that Home Assistant starts without integration setup or platform errors.

## HACS installation

Users can add this repository in HACS under **Integrations → Custom repositories**, using category **Integration**, then download the integration and restart Home Assistant. Adding a custom repository makes it available to that user's HACS instance; it does not automatically add it to the official HACS default catalog.

## Validation limits

The GitHub Actions checks cover Python syntax, metadata JSON/YAML syntax, Home Assistant's hassfest checks, and HACS repository validation. Passing CI does not replace an end-to-end test in a running Home Assistant instance or confirm that third-party APIs and OAuth-style authorization callbacks are working.
