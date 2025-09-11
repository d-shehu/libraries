import { Component, Input } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'lib-forbidden',
  standalone: true,
  imports: [RouterModule, MatIconModule, MatButtonModule],
  templateUrl: './forbidden.html',
  styleUrl: './forbidden.css'
})
export class Forbidden {
  @Input() title: string = '403 Forbidden';
  @Input() message: string = 'You do not have permission to access this part of the app.';
  @Input() icon: string = 'block';

  @Input() buttonText: string = 'Go Home';
  @Input() buttonHref: string = '/'; //Default path
}
