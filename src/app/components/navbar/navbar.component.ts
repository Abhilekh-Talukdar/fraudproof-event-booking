import { Component } from '@angular/core';
import { Observable } from 'rxjs';
import { AuthService, AuthUser } from '../../services/auth.service';

@Component({
  selector: 'app-navbar',
  standalone: false,
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.css'
})
export class NavbarComponent {
  user$: Observable<AuthUser | null>;

  constructor(private auth: AuthService) {
    this.user$ = this.auth.user$;
    this.auth.refresh().subscribe();
  }

  logout(): void {
    this.auth.logout().subscribe();
  }

}
