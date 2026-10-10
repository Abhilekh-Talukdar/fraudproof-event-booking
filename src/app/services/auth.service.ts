import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, catchError, of, tap, map } from 'rxjs';

export type UserRole = 'USER' | 'ORGANIZER' | 'SCANNER' | 'ADMIN';

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  status: 'ACTIVE' | 'DISABLED';
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly userSubject = new BehaviorSubject<AuthUser | null>(null);
  readonly user$ = this.userSubject.asObservable();

  refresh(): Observable<AuthUser | null> {
    return this.http.get<{ user: AuthUser }>('/api/me').pipe(
      map(response => response.user),
      tap(user => this.userSubject.next(user)),
      tap({ error: () => this.userSubject.next(null) }),
      catchError(() => of(null))
    );
  }

  login(email: string, password: string): Observable<{ user: AuthUser }> {
    return this.http.post<{ user: AuthUser }>('/api/auth/login', { email, password }).pipe(
      tap(response => this.userSubject.next(response.user))
    );
  }

  register(email: string, password: string): Observable<{ user: AuthUser }> {
    return this.http.post<{ user: AuthUser }>('/api/auth/register', { email, password }).pipe(
      tap(response => this.userSubject.next(response.user))
    );
  }

  logout(): Observable<void> {
    return this.http.post<void>('/api/auth/logout', {}).pipe(tap(() => this.userSubject.next(null)));
  }
}
