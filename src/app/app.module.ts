import { NgModule } from '@angular/core';
import { BrowserModule, provideClientHydration, withEventReplay } from '@angular/platform-browser';
import { provideHttpClient } from '@angular/common/http'; // Import HttpClientModule   
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { EventListComponent } from './components/event-list/event-list.component';
import { EventDetailComponent } from './components/event-detail/event-detail.component';
import { NavbarComponent } from './components/navbar/navbar.component';

@NgModule({
  declarations: [
    AppComponent,
    EventListComponent,
    EventDetailComponent,
    NavbarComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
  ],
  providers: [
    provideClientHydration(withEventReplay()),
    provideHttpClient(), // Provide HttpClient
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
