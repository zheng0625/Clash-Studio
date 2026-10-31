import { catalogue as desktopCatalogue, standaloneIds as desktopStandalone } from './catalogue'
import { androidCatalogue } from './android-catalogue'
export const androidWorkshop=location.pathname.endsWith('/ui-android-components.html')
export const catalogue=androidWorkshop?androidCatalogue:desktopCatalogue
export const standaloneIds=androidWorkshop?[]:desktopStandalone
export const workshopPath=androidWorkshop?'/ui-android-components.html':'/ui-components.html'
