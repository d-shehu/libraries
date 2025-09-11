import { Component, Input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-not-found-page',
  standalone: true,
  imports: [RouterModule, MatIconModule, MatButtonModule],
  templateUrl: './not-found.html',
  styleUrls: ['./not-found.html']
})
export class NotFound {
  @Input() title: string = '404 Not Found';
  @Input() message: string = "Sorry, we couldn't find that page.";
  @Input() icon: string = 'search_off';

  @Input() buttonText: string = 'Go Home';
  @Input() buttonHref: string = '/'; //Default page
}