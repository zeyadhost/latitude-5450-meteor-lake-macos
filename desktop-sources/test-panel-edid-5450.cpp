#include "latitude_panel_edid_5450.h"
#include <assert.h>
#include <string.h>
#include <math.h>
#include <stdio.h>
int main(){
 uint32_t w=0,h=0;assert(latitudeEDIDGeometry(latitudePanelEDID,128,1920,1080,&w,&h));assert(w==309&&h==174);
 assert(round(hypot((double)w,h)/25.4*10)/10==14.0);
 assert(!latitudeEDIDGeometry(latitudePanelEDID,127,1920,1080,&w,&h));assert(!latitudeEDIDGeometry(latitudePanelEDID,128,2560,1440,&w,&h));
 uint8_t e[128];memcpy(e,latitudePanelEDID,128);e[50]^=1;assert(!latitudeEDIDGeometry(e,128,1920,1080,&w,&h));
 memcpy(e,latitudePanelEDID,128);e[0]=1;e[127]--;assert(!latitudeEDIDGeometry(e,128,1920,1080,&w,&h));
 memcpy(e,latitudePanelEDID,128);e[126]=1;e[127]--;assert(!latitudeEDIDGeometry(e,128,1920,1080,&w,&h));
 assert(!latitudeEDIDGeometry(nullptr,128,1920,1080,&w,&h));assert(!latitudeEDIDGeometry(latitudePanelEDID,128,1920,1080,nullptr,&h));
 puts("PASS captured EDID checksum/native-mode/309x174mm/14-inch geometry (Latitude 5450 AUO panel); malformed/truncated/mismatched data rejected. No hardware access.");
}
