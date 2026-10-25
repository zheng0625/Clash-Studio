pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "ClashStudioAndroid"
include(":app")
if (providers.gradleProperty("includeVpnProbe").orNull == "true") include(":vpn-probe")
if (providers.gradleProperty("includeLifecycleProbe").orNull == "true") include(":lifecycle-probe")
