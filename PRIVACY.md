# Privacy and data handling

Applies to the session-handoffs package published by Compound Labs. Updated October 27, 2026.

## Package behavior

Stores local prompt/receipt files with private permissions; invokes the user’s installed destination CLI. The destination CLI processes the prompt under its existing provider account/settings. Prompts can appear in OS process inspection and normal client history. No independent telemetry.

The package does not operate a separate account system or publisher-run data collection service. Your AI assistant, model provider, package manager, browser, and any website or dependency service you choose to use have their own data-handling policies. Using this package does not change those settings or policies.

## Your control

Choose which tasks, files, and routes you authorize the host to access. Review local outputs and remove them when no longer needed. Keep secrets and private project material out of public issue reports. Files and provider histories may remain until you delete them through the relevant filesystem or service; the package does not delete those records automatically.

## Support and terms

For a question about this package, use the [repository issues](https://github.com/kyisaiah47/session-handoffs/issues) without including sensitive data. Permission to install, use, and privately adapt the package is governed by [LICENSE](LICENSE).
