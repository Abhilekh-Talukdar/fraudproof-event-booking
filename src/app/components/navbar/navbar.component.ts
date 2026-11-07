import { Component, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
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

  constructor(private auth: AuthService, @Inject(PLATFORM_ID) platformId: object) {
    this.user$ = this.auth.user$;
    if (isPlatformBrowser(platformId)) {
      this.auth.refresh().subscribe();
    }
  }

  logout(): void {
    this.auth.logout().subscribe();
  }

}
