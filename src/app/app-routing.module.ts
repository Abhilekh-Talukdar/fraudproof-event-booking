import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { EventListComponent } from './components/event-list/event-list.component';
import { EventDetailComponent } from './components/event-detail/event-detail.component';

const routes: Routes = [
  { path: 'events', component: EventListComponent },
  { path: 'events/:id', component: EventDetailComponent }, // Route for event details
  { path: '', redirectTo: '/events', pathMatch: 'full' }, // Default route
  { path: '**', redirectTo: '/events' } // Wildcard route (optional)
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
