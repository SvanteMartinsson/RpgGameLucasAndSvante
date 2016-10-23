import java.util.Scanner;

public class Fight {
	
	boolean loop;
	
	Scanner scanner = new Scanner(System.in);
	
	int input;
	
	
	public void fight(GameObject player, GameObject enemy){
		loop = true;
		while(loop){
			
		System.out.println("HP: " + player.hp);
		System.out.println("Enemy HP: " + enemy.hp);
		System.out.println("Hit: 1");
		System.out.println("Try to dodge: 2");
		input = scanner.nextInt();
		
		if(input == 1){
			enemy.hp -= player.dmg;
		}else{
			
		}
		
		player.hp -= enemy.dmg;
		
		if(player.hp<=0){
			System.out.println("You died!");
			loop = false;
		}else if(enemy.hp <= 0){
			System.out.println("You killed the enemy!");
			loop = false;
		}
		}
		
	}
	
}
