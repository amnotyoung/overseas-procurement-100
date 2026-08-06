'use strict'

const SUCCESS_STATUS = 'succeed'
const FINAL_FAILURES = new Map([
  ['deployment_failed', 'Deployment failed.'],
  ['deployment_perms_error', 'Deployment failed because of file permissions.'],
  ['deployment_content_failed', 'Deployment artifact content was rejected.'],
  ['deployment_cancelled', 'Deployment was cancelled.'],
  ['deployment_lost', 'Deployment stopped reporting status.']
])

function positiveInteger(value, fallback) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

function wait(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds))
}

module.exports = async function deployPagesLongWait({ github, context, core }) {
  const owner = context.repo.owner
  const repo = context.repo.repo
  const artifactId = positiveInteger(process.env.PAGES_ARTIFACT_ID, 0)
  const timeoutMs = positiveInteger(process.env.PAGES_DEPLOY_TIMEOUT_MS, 30 * 60 * 1000)
  const reportingIntervalMs = positiveInteger(process.env.PAGES_DEPLOY_REPORTING_INTERVAL_MS, 5000)
  const maximumStatusErrors = positiveInteger(process.env.PAGES_DEPLOY_MAX_STATUS_ERRORS, 10)

  if (!artifactId) {
    throw new Error('PAGES_ARTIFACT_ID must contain the uploaded Pages artifact ID.')
  }

  let idToken
  try {
    idToken = await core.getIDToken()
  } catch (error) {
    throw new Error(`Unable to obtain the Pages OIDC token: ${error.message}`)
  }

  core.info(`Creating Pages deployment for ${context.sha} with artifact ${artifactId}.`)
  const response = await github.request('POST /repos/{owner}/{repo}/pages/deployments', {
    owner,
    repo,
    artifact_id: artifactId,
    pages_build_version: context.sha,
    oidc_token: idToken
  })

  const deployment = response.data
  const deploymentId =
    deployment.id || deployment.status_url?.split('/').pop() || context.sha
  core.setOutput('page_url', deployment.page_url || '')
  core.info(`Created Pages deployment ${deploymentId}; waiting up to ${Math.round(timeoutMs / 60000)} minutes.`)

  let deploymentPending = true
  let cancellationPromise = null

  async function cancelDeployment(reason) {
    if (!deploymentPending) return
    if (cancellationPromise) return cancellationPromise

    core.warning(`Cancelling Pages deployment ${deploymentId}: ${reason}`)
    cancellationPromise = github
      .request('POST /repos/{owner}/{repo}/pages/deployments/{pages_deployment_id}/cancel', {
        owner,
        repo,
        pages_deployment_id: deploymentId
      })
      .then(() => {
        deploymentPending = false
        core.info(`Cancelled Pages deployment ${deploymentId}.`)
      })
      .finally(() => {
        cancellationPromise = null
      })
    return cancellationPromise
  }

  function handleSignal(signal) {
    void cancelDeployment(`workflow received ${signal}`)
      .catch(error => core.warning(`Unable to cancel Pages deployment: ${error.message}`))
      .finally(() => process.exit(1))
  }

  const handleSigint = () => handleSignal('SIGINT')
  const handleSigterm = () => handleSignal('SIGTERM')
  process.once('SIGINT', handleSigint)
  process.once('SIGTERM', handleSigterm)

  const startedAt = Date.now()
  let consecutiveStatusErrors = 0

  try {
    while (Date.now() - startedAt < timeoutMs) {
      await wait(reportingIntervalMs)

      let statusResponse
      try {
        statusResponse = await github.request(
          'GET /repos/{owner}/{repo}/pages/deployments/{pages_deployment_id}',
          { owner, repo, pages_deployment_id: deploymentId }
        )
        consecutiveStatusErrors = 0
      } catch (error) {
        consecutiveStatusErrors += 1
        core.warning(
          `Unable to read Pages deployment status (${consecutiveStatusErrors}/${maximumStatusErrors}): ${error.message}`
        )
        if (consecutiveStatusErrors >= maximumStatusErrors) {
          try {
            await cancelDeployment('too many consecutive status errors')
          } catch (cancelError) {
            core.warning(`Unable to cancel Pages deployment: ${cancelError.message}`)
          }
          throw new Error('Too many consecutive errors while reading Pages deployment status.')
        }
        continue
      }

      const status = statusResponse.data.status
      core.info(`Current Pages deployment status: ${status}`)

      if (status === SUCCESS_STATUS) {
        deploymentPending = false
        core.info('Pages deployment reported success.')
        return
      }

      if (FINAL_FAILURES.has(status)) {
        deploymentPending = false
        throw new Error(FINAL_FAILURES.get(status))
      }
    }

    await cancelDeployment(`deployment did not finish within ${Math.round(timeoutMs / 60000)} minutes`)
    throw new Error('Pages deployment timed out.')
  } finally {
    process.removeListener('SIGINT', handleSigint)
    process.removeListener('SIGTERM', handleSigterm)
  }
}
