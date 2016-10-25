import java.util.Scanner;

public class Store {
	
	String[] itemList = new String[4];
	Scanner scanner = new Scanner(System.in);
	
	int itemId = 0;
	int buy;
	Player player;
	
	public Store(Player player){
		this.player = player;
	}
	
	public void initItems(){
		itemList[0] = "Hp potion";
		itemList[1] = "Sword";
		itemList[2] = "Axe";
		itemList[3] = "Longsword";
	}
	
	public void buyItems(){
		System.out.println("Welcome to the store!");
		System.out.println("-------------------------------");
		for(int i = 0; i<=3; i++){
			System.out.println(i+1 + ": " + itemList[i]);
		}
		System.out.println("-------------------------------");
		buy = scanner.nextInt();
		if(buy == 1 && player.gold >= 10){
			player.gold -= 10;
		}else if(buy == 2 && player.gold >= 50){
			player.gold -=50;
			player.dmg +=5;
		}else if(buy == 3 && player.gold >= 175){
			player.gold -=175;
			player.dmg += 13;
		}else if(buy == 4 && player.gold >= 350){
			player.gold -= 350;
			player.newWeapon(3);
		}
			
	}
	
}
