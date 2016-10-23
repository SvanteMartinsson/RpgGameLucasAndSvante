
public class Player extends GameObject{

	String[] inv = new String[3];
	int invSpot;
	int lastSpot = 0;
	int gold = 0;
	int xp = 0;
	// Lägg till pengar och xp variabler här och sätt dem till noll.
	// Gör även en level variabel som du sätter till 1
	
	public Player(int hp, int dmg, String name, String sex){
		this.hp = hp;
		this.dmg = dmg;
		this.name = name;
		this.sex = sex;

		dodgeChance = 4;
	}

	
	// Gör en level upgrade klass
	
	public void attack() {
		
		
	}
	
	public void addToInv(String item){
		inv[lastSpot] = item;
		lastSpot++;
	}
	
	public void deleteFromInv(){
		inv[lastSpot] = " ";
	}
	
	public void checkForItems(){
		for(int i = 0; i<lastSpot; i++){
			
			if(inv[i] == "knife"){
				dmg+=5;
				
			}
		}
	}
	
	public void displayInv(){
		
		// Displays the inventory with place number
		for(int i = 0; i<lastSpot; i++){
			invSpot = i+1;
			System.out.println(i+1 + " " + inv[i]);
		}
	}

}
