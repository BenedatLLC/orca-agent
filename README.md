# orca-agent
Orca-agent is an an agent for Observability Root Cause Analysis.
This first version reads Grafana alerts that were sent to a Slack channel,
and replies with an explanation and suggested debugging approaches. It uses
tools defined over the [Python kubernetes client APIs](https://github.com/kubernetes-client/python)
to find more specific details about the problems. If a runbook is provided in the alert,
it will use that in formulating a debugging strategy.

## Example output
Here is an explanation of the CrashLoopBackOff alert and next debugging steps, using actual data from your cluster:

---

### What Happened?

The pod **fraud-detection-779dc555c5-7ndxg** (container: fraud-detection) is currently in a CrashLoopBackOff. This means Kubernetes keeps trying to start the container, but it crashes quickly after every attempt.

#### Pod/Container Details

- **Image:** ghcr.io/open-telemetry/demo:2.0.2-fraud-detection
- **Restart count:** 662 (this is very high!)
- **Last container state:** Terminated with exit code 137 (which usually means killed due to out-of-memory, OOMKilled, or SIGKILL)
- **Current state:** Waiting ("CrashLoopBackOff"). Message: back-off 5m0s restarting failed container=fraud-detection...
- **Resource limits/requests:** 300Mi memory

#### Recent Events

- Normal: Image already present on machine (pull succeeded)
- Warning: BackOff restarting failed container fraud-detection

#### Recent Logs

The container log provides:
```
Picked up JAVA_TOOL_OPTIONS: -javaagent:/app/opentelemetry-javaagent.jar
OpenJDK 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended
[otel.javaagent 2025-07-14 02:30:06:603 +0000] [main] INFO io.opentelemetry.javaagent.tooling.VersionLogger - opentelemetry-javaagent - version: 2.13.3
```
No error messages are available in these logs, but the last container state has exit code 137.

---

### What Does Exit Code 137 Mean?

- **Exit Code 137** usually indicates the container was killed by the system, often for using too much memory (OOMKilled).
- Since your container is both requesting and being limited to 300Mi memory, and that matches what is allocated, it's likely this container is running out of memory very quickly.

---

### Immediate Steps to Debug & Resolve

1. **Check Resource Usage**
   The memory limits (300Mi) may be too low for this Java workload, especially with the OpenTelemetry agent.
   - Try increasing the memory `requests` and `limits` for this deployment (500Mi or more is often needed for Java apps).

2. **Check for OOMKilled Events**
   Although events above mention only 'BackOff', not explicit OOMKilled, the exit code strongly suggests OOM.
   - You can check for OOMKilled events using:
     ```
     kubectl get events --namespace=default --field-selector involvedObject.name=fraud-detection-779dc555c5-7ndxg
     ```
   - Or check the pod's status in more detail:
     ```
     kubectl describe pod fraud-detection-779dc555c5-7ndxg -n default
     ```

3. **Application Logs**
   If possible, try to view additional logs. The provided logs show nothing after JVM startup, further suggesting a rapid resource exhaustion.

4. **Review JVM Heap Settings**
   - Consider explicitly setting JVM heap settings according to the new container memory limit. For example, set `-Xmx` and `-Xms` to values safely below the requested container memory.

---

### Runbook and Additional Reference

This alert includes a runbook:
https://github.com/BenedatLLC/otel-demo/blob/main/RCA/CrashLoop.md
This gives detailed, step-by-step procedures for CrashLoopBackOff, specifically for OOMKilled and configuration errors.

---

#### How was this analysis done?

- Used kubectl-equivalent tooling (`get_pod_container_statuses`, `get_pod_events`, and `get_logs_for_pod_and_container`) to review the real pod/container status, events, and logs.
- Looked up the exit code and reviewed resource settings directly from the live cluster.
- Interpreted logs and state based on what is typically found for Java apps running with an OpenTelemetry agent.

---

**In summary:**
Your fraud-detection container is likely running out of memory on startup. Increase its memory limit and/or tune the JVM settings, then redeploy. If it continues to crash, check logs after adjusting, and consult the runbook linked above for more advanced troubleshooting.

## Prerequisites
### direnv
You need to have [direnv](https://direnv.net/) installed and configured for your shell.
This is used to manage environment variables for paths and secrets. Once you have
`direnv` set up, copy the file `envrc.template` to `.envrc` and set the files for your secrets.
After changing that file, you will need to call `direnv allow` to enable those settings.

### uv
[uv](https://docs.astral.sh/uv/) is a package and project manager for Python.

### Slack
This agent use's slacks [Python SDK](https://tools.slack.dev/python-slack-sdk/) to read
alerts that were published by Grafana to a specific slack channel (`#alerts` by default).
To use this, you need to set up a [Slack app](https://api.slack.com/quickstart) in your
workspace, and obtain a token. In your `.envrc` file, you should set the environment variable
`SLACK_BOT_TOKEN` to the value of this token.

### OpenAI
This example uses OpenAI GPT-4.1 as its default model. You will need to set the environment
variable `OPENAI_API_KEY` in your `.envrc` file to your OpenAI token. You can also use other
models, just specify the model on the command line for the aent and be sure to have any tokens defined in
`.envrc`.

## Running the agent
The agent can be run via `uv run orca-agent [options]`

The full usage is:
```
usage: orca-agent [-h] [--model MODEL] [--alert-slack-channel ALERT_SLACK_CHANNEL] [--agent-slack-user AGENT_SLACK_USER] [--alert-slack-user ALERT_SLACK_USER] [--last-check-time LAST_CHECK_TIME]
                  [--check-time-file CHECK_TIME_FILE] [--check-interval-seconds CHECK_INTERVAL_SECONDS] [--debug] [--log LOG] [--dry-run] [--dump-messages-and-exit]

An agent to reply to Grafana alerts with summaries and debugging tips.

options:
  -h, --help            show this help message and exit
  --model MODEL         Model to use for the agent (default: openai:gpt-4.1)
  --alert-slack-channel ALERT_SLACK_CHANNEL
                        Slack channel where alerts are sent (default: alerts)
  --agent-slack-user AGENT_SLACK_USER
                        Slack user name for the agent (default: orca-alerts)
  --alert-slack-user ALERT_SLACK_USER
                        Slack user name that sends alerts (default: Grafana notifications)
  --last-check-time LAST_CHECK_TIME
                        ISO formatted date or datetime for last check (default: None)
  --check-time-file CHECK_TIME_FILE
                        File to store last check time (default: last_check_time.txt)
  --check-interval-seconds CHECK_INTERVAL_SECONDS
                        Interval in seconds between checks (default: 300)
  --debug, -d           If specified, print additional debug information
  --log LOG             Logging level (e.g. DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: WARNING.
  --dry-run             If specified, do not send messages to Slack (dry run mode)
  --dump-messages-and-exit
                        If specified, print the markdown for all slack alert messages found and exit.
  --enable-tracing      Enable OpenTelemetry tracing with Phoenix.
```

When running it will check for new messages, process them, sleep for a specified interval (5 minutes, by default),
and then repeat this sequence.

### Other utilities
There is a utility to delete the reply messages: `delete-messages`.

## Phoenix integration for tracing
When running in the development environment, the necessary libraries have been installed to enable OpenTelemetry tracing
via a locally-hosted [Phoenix](https://github.com/Arize-ai/phoenix) instance. To use it, do the following:

1. Add the following to your .envrc file: `export PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006`
2. Run the docker container: `docker run -p 6006:6006 -p 4317:4317 -i -t arizephoenix/phoenix:latest`
3. When running `orca-agent`, specify the `--enable-tracing` option

## See also
[otel-demo](https://github.com/BenedatLLC/otel-demo) provides some scripts, instructions,
and root cause analyses around the
[Open Telemetry Demo Application](https://github.com/open-telemetry/opentelemetry-demo).
This application can be useful for testing the Orca agent.
