// src/app/app.module.ts
import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
// REMOVE HttpClientModule import
// import { HttpClientModule } from '@angular/common/http';
import { ReactiveFormsModule } from '@angular/forms';
import { provideHttpClient, withFetch } from '@angular/common/http'; // <-- IMPORT provideHttpClient

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { EventListComponent } from './components/event-list/event-list.component';
import { EventDetailComponent } from './components/event-detail/event-detail.component';
import { NavbarComponent } from './components/navbar/navbar.component';
import { BookingFormComponent } from './components/booking-form/booking-form.component';

@NgModule({
  declarations: [
    AppComponent,
    EventListComponent,
    EventDetailComponent,
    NavbarComponent,
    BookingFormComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    ReactiveFormsModule
    // REMOVE HttpClientModule from imports array
    // HttpClientModule
  ],
  providers: [
    // ADD provideHttpClient() to the providers array
    provideHttpClient(withFetch())
    // If you later add interceptors, it would look like:
    // provideHttpClient(withInterceptors([yourInterceptorFn])),
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }