import java.util.Random;
import java.util.Scanner;

public class Fight {
	
	boolean loop;
	
	int dodge;
	
	Scanner scanner = new Scanner(System.in);
	
	Random r = new Random();
	
	int input;
	
	
	public void fight(GameObject player, GameObject enemy){
		loop = true;
		while(loop){
			
		System.out.println("HP: " + player.hp);
		System.out.println("Enemy HP: " + enemy.hp);
		System.out.println("Power attack(30%): 1");
		System.out.println("Normal attack(55%): 2");
		System.out.println("Quick attack(75%): 3");
		input = scanner.nextInt();
		
		if(input == 1){
			if(r.nextInt(100 + 1) >= 70){
				enemy.hp -= 20;
			}else{
				System.out.println("The " + enemy.name + " dodged your attack!");
				if(r.nextInt(100)+1 >= 25){
					System.out.println("The " + enemy.name + " dealt " + enemy.dmg + " damage to you!");
					player.hp -= enemy.dmg;
				}
			}
		}else if(input == 2){
			if(r.nextInt(100 + 1) >= 45){
				enemy.hp -= 15;
			}else{
				System.out.println("The " + enemy.name + " dodged your attack!");
				if(r.nextInt(100)+1 >= 25){
					System.out.println("The " + enemy.name + " dealt " + enemy.dmg + " damage to you!");
					player.hp -= enemy.dmg;
				}
			}
		}else if(input == 3){
			if(r.nextInt(100 + 1) >= 25){
				enemy.hp -= enemy.dmg;
			}else if(r.nextInt(100 + 1) >= 25){
				System.out.println("The " + enemy.name + " dealt " + enemy.dmg + " damage to you!");
				player.hp -= enemy.dmg;
			}
		}
		
		if(player.hp<=0){
			System.out.println("You died!");
			player.hp = 100;
			loop = false;
		}else if(enemy.hp <= 0){
			System.out.println("You killed the enemy!");
			loop = false;
		}
		}
		
	}
	
}
